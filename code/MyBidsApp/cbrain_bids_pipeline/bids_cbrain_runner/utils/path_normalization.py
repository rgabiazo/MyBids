# bids_cbrain_runner/utils/path_normalization.py
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def _looks_like_absolute_path(value: str) -> bool:
    """Heuristic check for absolute paths (POSIX and Windows)."""
    if not value:
        return False
    value = value.strip()
    if value.startswith("/"):
        return True
    # Windows drive letter (C:\...)
    if len(value) > 2 and value[1] == ":" and value[0].isalpha():
        return True
    # UNC paths (\\server\share)
    if value.startswith("\\\\"):
        return True
    return False


def normalize_file_for_upload(
    local_path: Path,
    dataset_root: Path,
    temp_root: Path | None,
    cfg: Mapping[str, object] | None = None,
    *,
    dry_run: bool = False,
    root_rel: Path | None = None,
    flatten: bool = False,
) -> Path:
    """
    Return a path to a possibly normalized copy of *local_path*.

    The goal is to rewrite embedded *absolute* paths into forms that match
    how the file will appear on CBRAIN, without hard-coding any particular
    file type.
    """
    pn_cfg: Mapping[str, Any] = {}
    if isinstance(cfg, Mapping):
        pn_cfg = (cfg.get("path_normalization") or {})  # type: ignore[assignment]

    # Which extensions should be inspected for embedded paths?
    text_exts = pn_cfg.get("text_extensions") or [
        ".json",
        ".fsf",
        ".tsv",
        ".txt",
        ".csv",
    ]

    try:
        ext = local_path.suffix.lower()
    except Exception:  # pragma: no cover - super defensive
        return local_path

    if ext not in text_exts:
        return local_path

    if ext == ".json":
        # JSON handling is BIDS-specific (IntendedFor) and uses its own
        # config knob (intendedfor_relative_to).
        new_path = _normalize_bids_json(
            local_path,
            dataset_root,
            temp_root,
            pn_cfg,
            dry_run=dry_run,
        )
    else:
        # All other text extensions (.fsf, .tsv, .txt, .csv, .cfg, .sh, …)
        # are treated generically, using only root_rel + flatten.
        new_path = _normalize_generic_text(
            local_path,
            dataset_root,
            temp_root,
            pn_cfg,
            dry_run=dry_run,
            root_rel=root_rel,
            flatten=flatten,
        )

    return new_path or local_path


# ---------------------------------------------------------------------------
# JSON: BIDS IntendedFor normalisation
# ---------------------------------------------------------------------------


def _normalize_bids_json(
    local_path: Path,
    dataset_root: Path,
    temp_root: Path | None,
    pn_cfg: Mapping[str, Any],
    *,
    dry_run: bool = False,
) -> Path | None:
    """Rewrite absolute IntendedFor paths to CBRAIN-friendly relatives."""
    try:
        text = local_path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        logger.debug("[NORMALIZE] Skipping unreadable or non-JSON file %s", local_path)
        return None

    if not isinstance(data, dict) or "IntendedFor" not in data:
        return None

    strategy = str(
        pn_cfg.get("intendedfor_relative_to") or "subject-root"
    ).lower()
    drop_subject = strategy == "subject-root"

    ds_root = dataset_root.resolve()

    def _rewrite_item(item: object) -> object:
        if not isinstance(item, str):
            return item
        if not _looks_like_absolute_path(item):
            return item

        try:
            p = Path(item).resolve()
        except Exception:
            return item

        try:
            rel = p.relative_to(ds_root)
        except ValueError:
            # Not under the dataset root; leave untouched.
            return item

        parts = list(rel.parts)
        if drop_subject and parts and parts[0].startswith("sub-"):
            parts = parts[1:]
        if not parts:
            return item

        return "/".join(parts)

    original = data.get("IntendedFor")
    changed = False

    if isinstance(original, list):
        new_list = [_rewrite_item(v) for v in original]
        changed = new_list != original
        data["IntendedFor"] = new_list
    else:
        new_val = _rewrite_item(original)
        changed = new_val != original
        data["IntendedFor"] = new_val

    if not changed:
        return None

    if dry_run:
        logger.info(
            "[NORMALIZE] Would rewrite absolute 'IntendedFor' paths in %s",
            local_path,
        )
        return None

    ds_root = dataset_root.resolve()
    if temp_root is not None:
        try:
            rel = local_path.resolve().relative_to(ds_root)
        except ValueError:
            rel = Path(local_path.name)
        out_path = temp_root.joinpath(rel)
    else:
        out_path = local_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    logger.info(
        "[NORMALIZE] Rewrote absolute 'IntendedFor' paths in %s → %s",
        local_path,
        out_path,
    )
    return out_path


# ---------------------------------------------------------------------------
# Generic text handler (FSF, TSV, TXT, CFG, SH, …)
# ---------------------------------------------------------------------------


def _normalize_generic_text(
    local_path: Path,
    dataset_root: Path,
    temp_root: Path | None,
    pn_cfg: Mapping[str, Any],
    *,
    dry_run: bool = False,
    root_rel: Path | None = None,
    flatten: bool = False,
) -> Path | None:
    """
    Rewrite absolute paths in arbitrary text files (.fsf, .tsv, .txt, .csv,
    .cfg, .sh, …) using only:

      * dataset_root  – local BIDS root.
      * root_rel      – relative "userfile root" under dataset_root.
      * flatten       – whether to collapse to basenames.
    """
    try:
        text = local_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.debug("[NORMALIZE] Skipping unreadable text file %s", local_path)
        return None

    ds_root = dataset_root.resolve()
    root_rel_norm: Path | None
    if root_rel is None:
        root_rel_norm = None
    else:
        # Normalise things like "." into a Path but do *not* resolve
        # against the filesystem; this is purely dataset-relative.
        root_rel_norm = Path(str(root_rel))

    changed = False

    # Very simple heuristic: POSIX-style absolute path tokens (starting with /)
    path_token_re = re.compile(r"(/[^ \t\r\n\"'<>]+)")

    def _rewrite_token(token: str) -> str:
        nonlocal changed

        if not _looks_like_absolute_path(token):
            return token

        try:
            abs_p = Path(token).resolve()
        except Exception:
            return token

        try:
            rel = abs_p.relative_to(ds_root)
        except ValueError:
            # Not under the dataset root; leave untouched.
            return token

        # 1) Flattened uploads → always basenames.
        if flatten:
            new = os.path.basename(token)
        else:
            rel_parts = list(rel.parts)

            # 2) No specific root → dataset-root semantics.
            if root_rel_norm is None or str(root_rel_norm) in ("", "."):
                new = "/".join(rel_parts)

            else:
                # 3) Try to make the path relative to the given logical root.
                try:
                    rel2 = rel.relative_to(root_rel_norm)
                    rel2_parts = list(rel2.parts)
                    if rel2_parts:
                        new = "/".join(rel2_parts)
                    else:
                        # Degenerate case: path *is* the root itself.
                        new = os.path.basename(token)
                except ValueError:
                    # The absolute path is not under root_rel; fallback
                    # to dataset-root semantics.
                    new = "/".join(rel_parts)

        if new != token:
            changed = True
        return new

    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        return _rewrite_token(token)

    new_text = path_token_re.sub(repl, text)

    if not changed:
        return None

    if dry_run:
        logger.info(
            "[NORMALIZE] Would rewrite absolute paths in text file %s",
            local_path,
        )
        return None

    # Decide where to write the updated file.
    try:
        rel = local_path.resolve().relative_to(ds_root)
    except ValueError:
        rel = Path(local_path.name)

    if temp_root is not None:
        out_path = temp_root.joinpath(rel)
    else:
        out_path = local_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_text, encoding="utf-8")
    logger.info(
        "[NORMALIZE] Rewrote absolute paths in text file %s → %s",
        local_path,
        out_path,
    )
    return out_path
