"""Utilities for creating task aliases within BIDS datasets."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

logger = logging.getLogger(__name__)


@dataclass
class AliasSpec:
    """Specification for a task alias operation.

    Attributes:
        steps: Path components leading to the directory that contains
            subject folders.  Relative to the current working directory.
        old: Existing task label to be aliased.
        new: New task label to create.
        sub: Optional subject filter (e.g. ``"001"``).
        ses: Optional session filter (e.g. ``"01"``).
        json_mode: Behaviour for JSON sidecars: ``"copy"`` (default),
            ``"link"`` or ``"skip"``.
    """

    steps: List[str]
    old: str
    new: str
    sub: str | None = None
    ses: str | None = None
    json_mode: str = "copy"


def parse_alias_tokens(tokens: Sequence[str]) -> AliasSpec:
    """Return an :class:`AliasSpec` parsed from ``tokens``.

    Args:
        tokens: Sequence of CLI tokens supplied after ``--alias``.

    Returns:
        AliasSpec: Dataclass describing the alias operation.

    Raises:
        ValueError: If ``tokens`` are empty or malformed.
    """

    if not tokens:
        raise ValueError("--alias requires at least 'OLD=NEW'")

    *raw_steps, mapping = tokens
    # Allow callers to include placeholders like "sub-*", "ses-*" or "func" for
    # readability. These components do not correspond to real directories and
    # would otherwise cause the base path to be misinterpreted. Strip any
    # tokens containing wildcards as well as common BIDS hierarchy markers.
    steps = [s for s in raw_steps if "*" not in s and s not in {"func"}]

    parts = [p.strip() for p in mapping.split(',') if p.strip()]
    if not parts or '=' not in parts[0]:
        raise ValueError("alias mapping must be of the form OLD=NEW")

    old, new = [p.strip() for p in parts[0].split('=', 1)]
    opts: dict[str, str] = {}
    for opt in parts[1:]:
        if '=' in opt:
            k, v = opt.split('=', 1)
            opts[k.strip()] = v.strip()

    json_mode = opts.get('json', 'copy')
    sub = opts.get('sub')
    ses = opts.get('ses')

    return AliasSpec(list(steps), old, new, sub=sub, ses=ses, json_mode=json_mode)


# ---------------------------------------------------------------------------
# Core functionality
# ---------------------------------------------------------------------------

def _replace_strings(obj: object, old: str, new: str) -> object:
    """Recursively replace substrings in JSON-like structures.

    Args:
        obj: Mapping, sequence or string to process.
        old: Original substring to replace.
        new: Replacement substring.

    Returns:
        The updated structure with substitutions applied.
    """

    if isinstance(obj, dict):
        return {k: _replace_strings(v, old, new) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_strings(v, old, new) for v in obj]
    if isinstance(obj, str):
        return obj.replace(old, new)
    return obj


def make_task_aliases(spec: AliasSpec, *, dry_run: bool = False) -> None:
    """Create task aliases according to ``spec``.

    The function walks all ``sub-*``/``ses-*`` directories beneath
    ``spec.steps`` and creates aliases for files with ``task-<old>`` in
    their name. Non-JSON files become relative symlinks. JSON sidecars
    are copied with in-content replacements or, optionally, linked or
    skipped.

    Args:
        spec: Description of the alias operation.
        dry_run: When ``True``, log intended actions without modifying files.

    Returns:
        None.
    """

    base_dir = Path(os.getcwd())
    if spec.steps:
        base_dir = base_dir.joinpath(*spec.steps)
    if not base_dir.exists():
        logger.warning("[ALIAS] Base directory '%s' not found", base_dir)
        return

    subs: Iterable[Path]
    if spec.sub:
        subs = [base_dir / f"sub-{spec.sub}"]
    else:
        subs = [p for p in base_dir.glob('sub-*') if p.is_dir()]

    for sub_dir in subs:
        if not sub_dir.is_dir():
            continue
        ses_dirs: Iterable[Path]
        if spec.ses:
            ses_dirs = [sub_dir / f"ses-{spec.ses}"]
        else:
            ses_dirs = [p for p in sub_dir.glob('ses-*') if p.is_dir()]

        for ses_dir in ses_dirs:
            if not ses_dir.is_dir():
                continue
            func_dir = ses_dir / 'func'
            target_dir = func_dir if func_dir.is_dir() else ses_dir
            if not target_dir.is_dir():
                continue
            logger.info("Processing %s", target_dir)
            for src in target_dir.glob(f"*task-{spec.old}*"):
                dest_name = src.name.replace(f"task-{spec.old}", f"task-{spec.new}")
                dest = src.parent / dest_name
                if dest.exists():
                    if src.suffix == '.json' and dest.is_symlink() and spec.json_mode == 'copy':
                        if not dry_run:
                            dest.unlink()
                    else:
                        continue
                if src.suffix == '.json':
                    if spec.json_mode == 'skip':
                        continue
                    if spec.json_mode == 'link':
                        rel = os.path.relpath(src, dest.parent)
                        if dry_run:
                            logger.info("[DRY] Would symlink %s -> %s", dest, rel)
                        else:
                            os.symlink(rel, dest)
                            logger.info("ALIAS %s -> %s", dest, src)
                    else:  # copy
                        if dry_run:
                            logger.info("[DRY] Would copy JSON %s -> %s", src, dest)
                        else:
                            try:
                                with open(src) as fh:
                                    data = json.load(fh)
                                data = _replace_strings(data, spec.old, spec.new)
                                with open(dest, 'w') as fh:
                                    json.dump(data, fh, indent=2, sort_keys=True)
                                logger.info("JSON %s -> %s", src, dest)
                            except Exception as exc:  # pragma: no cover - unlikely
                                logger.error("[ALIAS] Failed to copy %s: %s", src, exc)
                else:
                    rel = os.path.relpath(src, dest.parent)
                    if dry_run:
                        logger.info("[DRY] Would symlink %s -> %s", dest, rel)
                    else:
                        os.symlink(rel, dest)
                        logger.info("ALIAS %s -> %s", dest, src)


def run_aliases(specs: Iterable[AliasSpec], *, dry_run: bool = False) -> None:
    """Execute a sequence of alias operations."""

    for spec in specs:
        make_task_aliases(spec, dry_run=dry_run)
