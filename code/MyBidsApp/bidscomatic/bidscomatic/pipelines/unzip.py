"""
Extraction helper for study archives (ZIP / TAR / TGZ / TBZ, …).

The function :pyfunc:`unzip_archives` unpacks every archive found under the
supplied *src* path and returns a compact report object
(:class:`~bidscomatic.pipelines.types.UnzipResult`).  Optional post-extraction
cleanup can be carried out by CLI wrappers that consume this report.

Revision history
----------------
    * Stray-folder sweep 2.0: if **no** archives exist under *src*, the helper
      now searches for child directories that contain at least one ``*.dcm`` or
      ``*.ima`` file at any depth so that `--rm-dcm-dirs` still works even
      after manual archive deletion.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path
from typing import Set
from zipfile import is_zipfile

from bidscomatic.pipelines.discovery import is_image_series
from bidscomatic.utils.archive import looks_like_archive
from .types import UnzipResult

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 0 – discovery helpers
# ---------------------------------------------------------------------------


def _is_archive(path: Path) -> bool:
    """Return ``True`` when *path* has an archive-like extension."""
    return looks_like_archive(path)


def _discover_archives(path: Path) -> list[Path]:
    """Return every archive under *path* (recursive when *path* is a directory)."""
    if _is_archive(path):                       # single file mode
        return [path]
    if path.is_dir():                           # directory tree mode
        return sorted(p for p in path.rglob("*") if _is_archive(p))
    raise ValueError(f"{path} is neither archive nor directory")


# ---------------------------------------------------------------------------
# 1 – archive introspection
# ---------------------------------------------------------------------------


def _list_archive_roots(archive: Path, logger: logging.Logger) -> Set[Path]:
    """Collect first-level directory names declared inside *archive*."""
    roots: set[str] = set()
    try:
        if tarfile.is_tarfile(archive):
            with tarfile.open(archive) as tf:
                roots = {Path(m.name).parts[0] for m in tf.getmembers() if m.name}
        elif is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                roots = {Path(n).parts[0] for n in zf.namelist() if n}
    except Exception as exc:
        # Best-effort only – failures are logged and do not abort extraction
        logger.warning("Could not inspect %s to collect dir roots: %s", archive, exc)
    return {Path(r) for r in roots if r and r != "."}


# ---------------------------------------------------------------------------
# 2 – extraction worker
# ---------------------------------------------------------------------------


def _run(cmd: list[str], kind: str) -> None:
    """Run *cmd* and propagate a non-zero return code as ``RuntimeError``."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"{kind} failed (code={result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


def _safe_unpack(
    archive: Path,
    dest: Path,
    *,
    logger: logging.Logger,
    list_files: bool,
) -> Set[Path]:
    """Extract *archive* into *dest* and return candidate DICOM root directories."""
    archive = archive.expanduser().resolve()
    dest = dest.expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    # Snapshot of directories present *before* extraction
    before_dirs = {d for d in dest.rglob("*") if d.is_dir()}

    # --------- actual extraction -----------------------------------------
    try:
        if is_zipfile(archive):
            logger.info("Unzipping ZIP: %s → %s", archive, dest)
            _run(["unzip", "-o", str(archive), "-d", str(dest)], "unzip")
        elif tarfile.is_tarfile(archive):
            logger.info("Unpacking TAR: %s → %s", archive, dest)
            _run(["tar", "-xf", str(archive), "-C", str(dest)], "tar")
        else:
            # Fallback to Python's shutil for rare formats
            logger.info("Unpacking (shutil): %s → %s", archive, dest)
            shutil.unpack_archive(str(archive), str(dest))
    except Exception as exc:
        logger.error("Failed to unpack %s: %s", archive, exc)
        raise

    # --------- 1) directories created during extraction -------------------
    after_dirs = {d for d in dest.rglob("*") if d.is_dir()}
    new_dirs = after_dirs - before_dirs

    # First directory component for each new path
    top_roots: set[Path] = {
        dest / Path(d.relative_to(dest)).parts[0] for d in new_dirs if d != dest
    }

    # --------- 2) directories advertised inside the archive ---------------
    top_roots.update(dest / r for r in _list_archive_roots(archive, logger))

    # --------- 3) optional file listing -----------------------------------
    if list_files:
        before_files = {f for f in dest.rglob("*") if f.is_file()}
        added_files = [
            p for p in dest.rglob("*") if p.is_file() and p not in before_files
        ]
        for f in sorted(added_files):
            logger.info("Extracted file: %s", f)

    return top_roots


# ---------------------------------------------------------------------------
# 3 – fallback helpers (stray DICOM trees)
# ---------------------------------------------------------------------------


def _contains_dicom_files(p: Path, *, max_checks: int = 50) -> bool:
    """Return ``True`` once a ``*.dcm`` / ``*.ima`` file is found within *p*."""
    checks = 0
    for f in p.rglob("*"):
        if f.is_file() and f.suffix.lower() in {".dcm", ".ima"}:
            return True
        checks += 1
        if checks >= max_checks:
            break
    return False


# ---------------------------------------------------------------------------
# 4 – public entry point
# ---------------------------------------------------------------------------


def unzip_archives(
    src: Path,
    logger: logging.Logger | None = None,
    *,
    list_files: bool = False,
) -> UnzipResult:
    """Recursively extract archives under *src* and collect a summary.

    Parameters
    ----------
    src
        File or directory to process.  A directory is searched recursively.
    logger
        Existing :pyclass:`logging.Logger` to attach messages to.  When *None*
        the module-level logger is used.
    list_files
        When *True*, every extracted file path is logged at INFO level.

    Returns
    -------
    UnzipResult
        Summary object containing key paths for optional follow-up cleanup.
    """
    logger = logger or log
    src = src.expanduser().resolve()

    try:
        archives = _discover_archives(src)
    except Exception as exc:
        logger.error("Could not discover archives under %s: %s", src, exc)
        raise

    logger.info("Found %d archive(s) under %s", len(archives), src)

    extracted_dirs: set[Path] = set()
    dcm_roots: set[Path] = set()

    # ------------------------ normal archive flow -------------------------
    for arc in archives:
        out_dir = arc.parent
        logger.info("About to unpack: %s → %s", arc, out_dir)

        roots = _safe_unpack(arc, out_dir, logger=logger, list_files=list_files)
        extracted_dirs.add(out_dir)
        dcm_roots.update(roots)

    # ------------------------ fallback: stray folders ---------------------
    if not archives:
        for child in src.iterdir():
            if child.is_dir() and (
                is_image_series(child) or _contains_dicom_files(child)
            ):
                logger.debug("Found stray DICOM folder: %s", child)
                dcm_roots.add(child)

    return UnzipResult(
        src=src,
        archive_dirs=sorted(extracted_dirs),
        archives=archives,
        dcm_roots=sorted(dcm_roots),
    )


# ---------------------------------------------------------------------------
__all__ = ["unzip_archives"]
