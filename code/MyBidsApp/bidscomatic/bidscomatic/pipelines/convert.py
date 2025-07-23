"""
High-level “DICOM → NIfTI” conversion built around *dcm2niix*.

The function :func:`convert_dicom_tree` walks an arbitrary directory tree,
launches *dcm2niix* in parallel, and moves the generated NIfTIs into a
deterministic folder structure under ``<BIDS_ROOT>/sourcedata/nifti``.
"""

from __future__ import annotations

# ───────── standard-library / third-party imports ─────────
import logging
import re
import unicodedata
from importlib import resources
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Iterable, List, Optional

import yaml
import pydicom

# Inner-package helpers
from bidscomatic.utils.slug import build_cleanup_regex, clean_slug
from ..io.dcm2niix import run_dcm2niix, _which_dcm2niix
from .discovery import (
    guess_sub_ses,
    _pick_date_from_path,
    _pick_ses_from_path,
    is_image_series,
)
from .types import Dcm2NiixResult

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants / regexes
# ─────────────────────────────────────────────────────────────────────────────
_SCRATCH_PREFIX = ".tmp_niix_"                 # Prefix for all TemporaryDirectory names
_SLUG_RE = re.compile(r"[^\w\-]+")

# YAML-driven slug cleanup rules ------------------------------------------------
with resources.files("bidscomatic.resources").joinpath("default_series.yaml").open() as fh:
    _YAML_CFG = yaml.safe_load(fh) or {}

_SUFFIXES: tuple[str, ...] = tuple(
    _YAML_CFG.get("slug_cleanup", {}).get("suffixes", [])
)
_CLEAN_REGEX = build_cleanup_regex(_SUFFIXES)

# ─────────────────────────────────────────────────────────────────────────────
# Tiny utilities
# ─────────────────────────────────────────────────────────────────────────────
def ensure_out_root(path: Path | str) -> Path:
    """Resolve *path* and create the directory if needed.

    Args:
        path: Destination folder for converted NIfTIs.

    Returns:
        The resolved :class:`pathlib.Path` object.
    """
    dst = Path(path).expanduser().resolve()
    dst.mkdir(parents=True, exist_ok=True)
    return dst


def _slug(text: str) -> str:
    """Return a filesystem-safe slug derived from *text*."""
    ascii_txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _SLUG_RE.sub("_", ascii_txt).strip("_").lower() or "unnamed"


def _series_description(sdir: Path) -> str:
    """Return a cleaned slug of *SeriesDescription* for *sdir*.

    Falls back to the directory name when the DICOM header is missing or
    unreadable.
    """
    try:
        first = next(f for f in sdir.rglob("*") if f.is_file())
        hdr = pydicom.dcmread(first, stop_before_pixels=True, force=True)
        desc = str(getattr(hdr, "SeriesDescription", "")).strip()
    except Exception:   # pragma: no cover – robustness over strictness
        desc = ""

    slug = _slug(desc) if desc else _slug(sdir.name)
    return clean_slug(slug, _CLEAN_REGEX)


def _is_enabled(logger: logging.Logger, level: int) -> bool:
    """Return ``True`` when *logger* would emit *level*."""
    try:
        return logger.isEnabledFor(level)
    except AttributeError:                   # structlog 22.x shim
        underlying = getattr(logger, "_logger", None)
        return underlying.isEnabledFor(level) if underlying else False


def _require_dcm2niix() -> None:
    """Abort early if *dcm2niix* cannot be located on *PATH*."""
    _which_dcm2niix()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers – destination planning
# ─────────────────────────────────────────────────────────────────────────────
def _hierarchical_parent(
    sdir: Path,
    *,
    out_root: Path,
    sub: str,
    ses_hint: str | None,
) -> Path:
    """Return the parent directory for the *hierarchical* strategy."""
    ses_actual = ses_hint or _pick_ses_from_path(sdir)
    date_like = _pick_date_from_path(sdir)
    fallback = sdir.parent.name

    parts: list[str | Path] = [out_root, sub]
    if ses_actual:
        parts.append(ses_actual)
    parts.append(date_like or fallback)
    return Path(*parts)


def _slug_parent(out_root: Path, sub: str, ses_hint: str | None) -> Path:
    """Return the parent directory for the *slug-merge* strategy."""
    parts: list[str | Path] = [out_root, sub]
    if ses_hint:
        parts.append(ses_hint)
    return Path(*parts)


def _plan_destination(
    *,
    sdir: Path,
    strategy: str,
    slug2folder: Dict[tuple[str, str | None], Path],
    out_root: Path,
    sub: str,
    ses_hint: str | None,
) -> Path:
    """Compute the output directory for *sdir* according to *strategy*."""
    if strategy == "hierarchical":
        return _hierarchical_parent(
            sdir,
            out_root=out_root,
            sub=sub,
            ses_hint=ses_hint,
        ) / sdir.name

    if strategy == "slug-merge":
        parent = _slug_parent(out_root, sub, ses_hint)
        slug = _series_description(sdir)

        key = (slug, ses_hint)
        folder = slug2folder.setdefault(key, parent / slug)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    raise ValueError(f"Unknown strategy '{strategy}'")


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────
def convert_dicom_tree(  # noqa: C901 (complexity inherent to conversion)
    src: Path,
    out_root: Path,
    *,
    threads: int = 4,
    sub: str | None = None,
    ses: str | None = None,
    merge_by_name: bool = False,
    logger: logging.Logger | None = None,
) -> List[Dcm2NiixResult]:
    """Recursively convert DICOM series under *src* into NIfTIs.

    Args:
        src: Directory tree containing one or more DICOM series.
        out_root: Destination root for NIfTI files.
        threads: Maximum number of concurrent *dcm2niix* jobs.
        sub: Explicit ``sub-XXX`` override.  When ``None`` the value is
            guessed from *src*.
        ses: Explicit ``ses-YYY`` override, or ``None`` to guess.
        merge_by_name: When ``True`` merge repeats with the same
            *SeriesDescription* into a single folder.
        logger: Optional custom :pyclass:`logging.Logger`.

    Returns:
        A list of :class:`~bidscomatic.pipelines.types.Dcm2NiixResult`
        objects—one per converted series.
    """
    lg = logger or logging.getLogger(__name__)
    src = src.expanduser().resolve()
    out_root = ensure_out_root(out_root)

    _require_dcm2niix()

    lg.info("Scanning %s for DICOM series …", src)
    series_dirs: List[Path] = [
        p for p in src.rglob("*") if p.is_dir() and is_image_series(p)
    ]
    lg.info("Found %d image series", len(series_dirs))
    if not series_dirs:
        lg.warning("Nothing to convert.")
        return []

    # ── Subject / session inference ───────────────────────────────────────
    if sub is None:
        sub, ses_guess = guess_sub_ses(src)
        ses = ses or ses_guess
    lg.info("Subject = %s    Session hint = %s", sub, ses or "<auto>")

    strategy = "slug-merge" if merge_by_name else "hierarchical"
    slug2folder: Dict[tuple[str, str | None], Path] = {}
    results: List[Dcm2NiixResult] = []

    # ---------------------------------------------------------------------
    # Worker helpers (inner functions keep outer scope variables in reach)
    # ---------------------------------------------------------------------
    def _scratch_dir(root: Path):
        """Return a TemporaryDirectory context manager with a fixed prefix."""
        return TemporaryDirectory(prefix=_SCRATCH_PREFIX, dir=root)

    def _convert_one(sdir: Path) -> Optional[Dcm2NiixResult]:
        """Run *dcm2niix* on *sdir* and move outputs to their final folder."""
        with _scratch_dir(out_root) as tmp:
            tmp_dir = Path(tmp)
            if _is_enabled(lg, logging.DEBUG):
                lg.debug("scratch dir = %s", tmp_dir)

            produced = run_dcm2niix(sdir, tmp_dir)
            if not produced:
                return None

            if _is_enabled(lg, logging.DEBUG):
                lg.debug("dcm2niix produced %d file(s) from %s", len(produced), sdir)
                for f in produced:
                    lg.debug("  • %s", f.name)

            dst = _plan_destination(
                sdir=sdir,
                strategy=strategy,
                slug2folder=slug2folder,
                out_root=out_root,
                sub=sub,
                ses_hint=ses or _pick_ses_from_path(sdir),
            )
            dst.mkdir(parents=True, exist_ok=True)

            moved: List[Path] = []
            for f in produced:
                target = dst / f.name
                # Resolve filename collisions by appending an incrementing suffix.
                if target.exists():
                    stem, suff = f.stem, f.suffix
                    i = 1
                    while (dst / f"{stem}_{i}{suff}").exists():
                        i += 1
                    target = dst / f"{stem}_{i}{suff}"
                f.replace(target)
                moved.append(target)

            return Dcm2NiixResult(src_dir=sdir, out_dir=dst, files=moved)

    # ---------------------------------------------------------------------
    # Thread pool
    # ---------------------------------------------------------------------
    with ThreadPoolExecutor(max_workers=max(1, threads)) as pool:
        fut2dir = {pool.submit(_convert_one, d): d for d in series_dirs}
        for fut in as_completed(fut2dir):
            try:
                res = fut.result()
                if res:
                    results.append(res)
            except Exception as exc:   # pragma: no cover – visible error path
                lg.error("Conversion failed for %s: %s", fut2dir[fut], exc)

    lg.info(
        "✓ %d series → %d file(s) written under %s",
        len(results),
        sum(len(r.files) for r in results),
        out_root,
    )

    return results
