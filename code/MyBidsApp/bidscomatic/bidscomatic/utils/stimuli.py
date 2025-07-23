"""Functions to copy stimulus files into a dataset while logging actions."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

__all__ = ["copy_stimuli"]


def copy_stimuli(paths: Iterable[Path], dest: Path, *, search_root: Path | None = None) -> int:
    """Copy stimulus files into *dest*, skipping existing ones.

    Args:
        paths: Iterable of stimulus paths as found in behavioural sheets.
        dest: Destination ``stimuli`` directory under the dataset root.
        search_root: Optional base directory used when stimulus paths are
            relative.

    Returns:
        int: Number of files copied.
    """
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    seen: set[str] = set()

    for raw in paths:
        src = raw
        if not src.is_absolute():
            base = search_root or Path()
            src = (base / raw).resolve()
        if src.name in seen:
            continue
        seen.add(src.name)
        if not src.exists():
            log.warning("[stimuli] missing %s", src)
            continue
        dst = dest / src.name
        if dst.exists():
            log.info("[stimuli] %s exists – skipped", dst.relative_to(dest.parent))
            continue
        try:
            shutil.copy2(src, dst)
            log.info("[stimuli] copied %s", dst.relative_to(dest.parent))
            copied += 1
        except Exception as exc:  # noqa: BLE001
            log.error("[stimuli] failed to copy %s: %s", src, exc)
    return copied
