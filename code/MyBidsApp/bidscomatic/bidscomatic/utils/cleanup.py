"""Utility helpers for removing study archives and accompanying DICOM folders.

The helpers perform destructive filesystem operations only (pure deletion)
and do not touch any other external state. Doing so keeps the
functions trivial to test: unit-tests simply create temporary files / folders,
invoke the helpers, and assert on the filesystem afterwards.

The design goals are:
    * **Side-effect isolation** – no logging configuration, no CLI prompts.
    * **Informative logging** – each attempted deletion is emitted through the
      central project logger at *INFO* or *ERROR* level, so every caller keeps
      a consistent breadcrumb trail.
    * **Dry-run support** – callers can preview destructive actions by setting
      ``dry=True`` which converts all deletions into no-ops while still
      logging what *would* have happened.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable, List

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# _rm_file / _rm_dir – internal primitives
# ─────────────────────────────────────────────────────────────────────────────

def _rm_file(path: Path, *, dry: bool) -> bool:
    """Attempt to unlink *path* and report the outcome through *log*.

    Args:
        path: Absolute or relative path to the file slated for removal.
        dry:  When *True* **no** deletion is performed – an *INFO* message is
              emitted instead.  This is primarily used by CLI callers that
              expose a `--dry-run` flag.

    Returns:
        *True* when the file really vanished, *False* otherwise (including
        dry-run mode and any exception raised by :py:meth:`Path.unlink`).
    """
    if dry:
        log.info("[dry-run] would delete %s", path)
        return False

    try:
        path.unlink(missing_ok=False)
        log.info("Deleted %s", path)
        return True
    except Exception as exc:  # pragma: no cover – log+return keeps behavior
        log.error("Could not delete %s: %s", path, exc)
        return False


def _rm_dir(path: Path, *, dry: bool) -> bool:
    """Recursively remove *path* via :pyfunc:`shutil.rmtree`.

    The function mirrors :func:`_rm_file` semantics but operates on *folders*.
    It exists as a small wrapper so higher-level helpers do not need to care
    whether they are dealing with files or directories.
    """
    if dry:
        log.info("[dry-run] would delete directory %s", path)
        return False

    try:
        shutil.rmtree(path)
        log.info("Deleted directory %s", path)
        return True
    except Exception as exc:  # pragma: no cover
        log.error("Could not delete %s: %s", path, exc)
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Public helpers – thin, composable wrappers around the primitives above
# ─────────────────────────────────────────────────────────────────────────────

def delete_archives(paths: Iterable[Path], *, dry: bool = False) -> List[Path]:
    """Remove every archive file in *paths* and return those actually deleted.

    Args:
        paths:  Arbitrary iterable of :class:`pathlib.Path` objects.  Paths that
                do not exist are skipped silently (deletion can only fail for
                existing files).
        dry:    Propagated to the internal `_rm_file` helper.  When *True* no
                file system mutation occurs.

    Returns:
        List of archive paths for which deletion succeeded.  The return value
        is suitable for post-hoc reporting (e.g. *n* of *m* removed).
    """
    deleted: list[Path] = []
    for arc in paths:
        # Skip missing files to avoid noisy log output in dry-run mode.
        if arc.exists() and _rm_file(arc, dry=dry):
            deleted.append(arc)
    return deleted


def delete_dcm_roots(roots: Iterable[Path], *, dry: bool = False) -> List[Path]:
    """Recursively remove every directory in *roots*.

    The semantics are identical to :func:`delete_archives` but operate on
    directories instead of individual files.

    Args:
        roots:  Iterable of paths that *should* be DICOM study roots.  The
                caller is responsible for deciding which directories are safe
                to remove.
        dry:    See :func:`delete_archives`.

    Returns:
        List containing only the directories whose removal completed without
        raising an exception.
    """
    deleted: list[Path] = []
    for d in roots:
        if d.exists() and _rm_dir(d, dry=dry):
            deleted.append(d)
    return deleted
