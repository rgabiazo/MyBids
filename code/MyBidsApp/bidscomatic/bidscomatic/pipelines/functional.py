"""
Organise functional BOLD NIfTIs into final BIDS ``func/`` folders.

The module is intentionally pure: it only performs file discovery, selection,
and movement. Heavy lifting such as DICOM → NIfTI conversion, BIDS validation,
or statistical analysis lives elsewhere. This keeps the code easy to unit test
and re-use in notebooks or other pipelines.

Key behaviours
--------------
* The *run* entity (``run-01`` etc.) is injected **only** when multiple runs
  are transferred for the same subject/session/task/phase-encode bucket.
* Run selection delegates to :func:`bidscomatic.pipelines._selection.best_runs`
  so anatomical, diffusion, and functional logic stays identical.
* REST NIfTIs are handled separately; deletion of the non-selected runs is
  optional through the *delete_losers* flag.
* SBRef files (single-band reference) are handled explicitly:
  - they are never considered BOLD candidates;
  - the best SBRef (per dir bucket) is moved alongside the chosen BOLD as
    ``*_sbref.nii.gz`` with matching entities.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    DefaultDict,
    Dict,
    Iterable,
    List,
    Mapping,
    Sequence,
)

import nibabel as nib

from bidscomatic.config.schema import BIDSEntities, ConfigSchema, Sequence as YSeq
from bidscomatic.models import BIDSPath
from bidscomatic.pipelines.types import SubjectSession
from bidscomatic.pipelines._selection import best_runs  # unified selection helper
from bidscomatic.pipelines._meta import (
    clear_meta_cache,
    is_sbref_nifti,
    task_name_of,
    dir_label_of,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants and regular expressions
# ---------------------------------------------------------------------------
# Patterns for extracting a numeric index from filenames. Ordered by how
# specific they are; the first match wins.
_IDX_PATTERNS = (
    re.compile(r"_(?:AP|PA|LR|RL|SI)_(\d{2,})", re.I),  # rfMRI_AP_17.nii.gz
    re.compile(r"_i(\d{3,})", re.I),  # *_i0123.nii.gz
    re.compile(r"[^\d](\d{2,})$", re.I),  # *_15.nii.gz (trailing digits)
)

# Placeholder detection – used for stripping empty placeholders cleanly.
_PLACEHOLDER_RE = re.compile(r"\{(?P<key>\w+)(?::[^\}]+)?\}")

# Default value for whether loser REST runs are removed from *sourcedata*.
DELETE_LOSERS_DEFAULT = False

# ---------------------------------------------------------------------------
# Tiny enums / value objects
# ---------------------------------------------------------------------------
class PhaseDir(str, Enum):
    """Canonical phase-encoding directions handled by this module."""

    AP = "AP"
    PA = "PA"


@dataclass(slots=True)
class Dest:
    """Triple holding source and destination paths for one NIfTI pair."""

    src_nii: Path
    dst_nii: Path
    dst_json: Path


# ---------------------------------------------------------------------------
# Low-level helpers (single-file scope)
# ---------------------------------------------------------------------------


def _task_of(path: Path) -> str | None:
    """Return *task* label derived from the side-car JSON or *None*."""
    return task_name_of(path)


def _n_vols(p: Path) -> int:
    """Return the number of 4-D volumes or ``1`` for 3-D files."""
    img = nib.load(p)
    return img.shape[3] if img.ndim == 4 else 1


def _rank_nifti(p: Path) -> tuple[int, int]:
    """Return a tuple *(n_volumes, file_size)* for tie-break ranking."""
    return _n_vols(p), p.stat().st_size


def _filename_index(p: Path) -> int | None:
    """Extract a series/run index encoded in *p* or *None* when absent."""
    for pat in _IDX_PATTERNS:
        if (m := pat.search(p.stem)):
            return int(m.group(1))
    return None


def _pick_runs(paths: Sequence[Path]) -> list[Path]:
    """Return *paths* deterministically sorted for run enumeration."""
    return sorted(
        paths, key=lambda p: (_filename_index(p) or 9_999_999, p.stat().st_mtime)
    )


def _dir_token(p: Path) -> str | None:
    """Infer PE direction label for *p*.

    Preference:
      1) filename (dir-AP, _AP_, etc.)
      2) JSON PhaseEncodingDirection -> dir label (RAS assumption)
    """
    return dir_label_of(p)


# ---------------------------------------------------------------------------
# Entity-rendering helpers
# ---------------------------------------------------------------------------


def _strip_pref(text: str, pref: str) -> str:
    """Remove *pref* from *text* if present (case-sensitive)."""
    return text[len(pref) :] if isinstance(text, str) and text.startswith(pref) else text


def _remove_unused_placeholders(tmpl: str, tokens: Dict[str, Any]) -> str:
    """Remove placeholders whose corresponding token is empty or *None*."""

    def repl(match: re.Match[str]) -> str:
        key = match.group("key")
        return "" if tokens.get(key) in {"", None} else match.group(0)

    return _PLACEHOLDER_RE.sub(repl, tmpl)


def _render_entities(tmpl: BIDSEntities, **tokens) -> BIDSEntities:
    """Render a :class:`~bidscomatic.config.schema.BIDSEntities` template."""
    clean: Dict[str, Any] = {
        k: _strip_pref(v, f"{k}-") if isinstance(v, str) else v
        for k, v in tokens.items()
    }

    rendered: Dict[str, Any] = {}
    for field, raw in tmpl.model_dump().items():
        if not isinstance(raw, str):
            rendered[field] = raw
            continue

        safe_tmpl = _remove_unused_placeholders(raw, clean)
        try:
            rendered[field] = safe_tmpl.format(**clean)
        except (ValueError, KeyError):
            bare = _PLACEHOLDER_RE.sub(lambda m: "{" + m.group("key") + "}", safe_tmpl)
            rendered[field] = bare.format(**clean)

    return BIDSEntities(**rendered)


def _ensure_taskname(json_path: Path, task: str) -> None:
    """Guarantee *TaskName* exists in *json_path* (round-trip safe)."""
    json_path.parent.mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {}
    if json_path.exists() and json_path.stat().st_size:
        try:
            meta = json.loads(json_path.read_text())
        except Exception:
            meta = {}

    meta["TaskName"] = task
    json_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


def _move_or_skip(src: Path, dst: Path, *, overwrite: bool) -> None:
    """Move *src* → *dst* respecting *overwrite* semantics and log outcome."""
    if dst.exists() and not overwrite:
        log.info("%s exists – skipped", dst.relative_to(dst.anchor))
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    log.info("%s ↳ %s", src.relative_to(src.anchor), dst.relative_to(dst.anchor))


# ---------------------------------------------------------------------------
# SBRef helpers
# ---------------------------------------------------------------------------


def _collect_sbref_candidates(ss: SubjectSession, seq: YSeq, src_root: Path) -> List[Path]:
    """Return SBRef candidates for *ss* matching the parent functional *seq*."""
    subj_dir = src_root / ss.sub / (ss.ses or "")
    cands = sorted(subj_dir.rglob(f"{seq.sequence_id}*.nii.gz"))
    return [p for p in cands if is_sbref_nifti(p)]


def _pair_sbref_for_bold(sbrefs: Sequence[Path], bold: Path) -> Path | None:
    """Pick the most likely SBRef to pair with a specific BOLD run.

    Robustness:
      * ignores SBRef paths that no longer exist (e.g. already moved)
      * avoids crashing when indices are absent/unparseable
      * guards stat() for rare race conditions
    """
    # Filter out stale paths (important for multi-run pairing where SBRefs get moved)
    live = [p for p in sbrefs if p.exists()]
    if not live:
        return None

    b_idx = _filename_index(bold)

    def key(p: Path) -> tuple[int, int, float]:
        # Prefer same numeric index, then closest index, then newest mtime.
        p_idx = _filename_index(p)

        if b_idx is None:
            same = 0
            dist = 0
        else:
            same = 1 if (p_idx is not None and p_idx == b_idx) else 0
            dist = abs((p_idx or 9_999_999) - b_idx)

        try:
            mtime = p.stat().st_mtime
        except FileNotFoundError:
            # Should be rare; treat as very old so it loses tie-breaks.
            mtime = 0.0

        return (same, -dist, mtime)

    return max(live, key=key, default=None)


def _sbref_target_paths(dst_bold_nii: Path) -> tuple[Path, Path]:
    """Compute destination SBRef NIfTI and JSON paths from a BOLD destination."""
    dst_sbref_nii = dst_bold_nii.with_name(
        dst_bold_nii.name.replace("_bold.nii.gz", "_sbref.nii.gz")
    )
    dst_sbref_json = dst_sbref_nii.with_suffix("").with_suffix(".json")
    return dst_sbref_nii, dst_sbref_json


def _move_sbref_pair(sbref: Path, dst_bold_nii: Path, *, overwrite: bool, task_name: str) -> None:
    """Move SBRef NIfTI+JSON to sit alongside the moved BOLD."""
    dst_sbref_nii, dst_sbref_json = _sbref_target_paths(dst_bold_nii)

    _move_or_skip(sbref, dst_sbref_nii, overwrite=overwrite)

    sbref_json = sbref.with_suffix("").with_suffix(".json")
    if sbref_json.exists():
        _move_or_skip(sbref_json, dst_sbref_json, overwrite=overwrite)
    else:
        dst_sbref_json.parent.mkdir(parents=True, exist_ok=True)
        dst_sbref_json.touch(exist_ok=True)

    _ensure_taskname(dst_sbref_json, task_name)


# ---------------------------------------------------------------------------
# Directory-level helpers
# ---------------------------------------------------------------------------


def _best_subset(paths: list[Path], wanted: int | None) -> list[Path]:
    """Return the best subset of *paths* according to *wanted* volume filter."""
    return best_runs(paths, wanted_vols=wanted)


def _process_dir(
    group: list[Path],
    *,
    dir_token: str | None,
    task_name: str,
    seq: YSeq,
    ss: SubjectSession,
    dataset_root: Path,
    overwrite: bool,
    vol_filter: Mapping[str, int],
) -> None:
    """Handle one subject/session/dir-bucket by moving the chosen runs."""
    # Filter out SBRef from BOLD selection
    bold_candidates = [p for p in group if not is_sbref_nifti(p)]
    if not bold_candidates:
        log.info(
            "[%s %s] %s dir=%s → no BOLD candidates (only SBRef?)",
            ss.sub,
            ss.ses or "",
            task_name,
            dir_token or "<none>",
        )
        return

    chosen = _best_subset(bold_candidates, vol_filter.get(task_name))
    if not chosen:
        log.info(
            "[%s %s] %s dir=%s → nothing matched volume filter",
            ss.sub,
            ss.ses or "",
            task_name,
            dir_token or "<none>",
        )
        return

    # The *run* entity is only added when multiple runs survive the filter.
    add_run_entity = len(chosen) > 1

    # Pre-collect SBRef candidates once per bucket
    sbref_cands = [p for p in group if is_sbref_nifti(p)]

    dests: list[Dest] = []
    for run_idx, src in enumerate(_pick_runs(chosen), start=1):
        ents = _render_entities(
            seq.bids,
            sub=ss.sub,
            ses=ss.ses or "",
            task=task_name,
            dir=dir_token or "",
            run=(run_idx if add_run_entity else ""),
        )
        bp = BIDSPath(root=dataset_root, datatype="func", entities=ents)
        dests.append(
            Dest(
                src_nii=src,
                dst_nii=bp.path,
                dst_json=bp.path.with_suffix("").with_suffix(".json"),
            )
        )

    to_move = [d for d in dests if overwrite or not d.dst_nii.exists()]
    log.info(
        "[%s %s] %s dir=%s → %d run(s) to move, %d already present",
        ss.sub,
        ss.ses or "",
        task_name,
        dir_token or "<none>",
        len(to_move),
        len(dests) - len(to_move),
    )

    for d in dests:
        _move_or_skip(d.src_nii, d.dst_nii, overwrite=overwrite)

        src_json = d.src_nii.with_suffix("").with_suffix(".json")
        if src_json.exists():
            _move_or_skip(src_json, d.dst_json, overwrite=overwrite)
        else:
            if not d.dst_json.exists():
                log.warning("%s missing – creating minimal side-car", src_json.name)
            d.dst_json.parent.mkdir(parents=True, exist_ok=True)
            d.dst_json.touch(exist_ok=True)

        _ensure_taskname(d.dst_json, task_name)

        # Pair and move SBRef, if available.
        # IMPORTANT: consume SBRef candidates so we don't reuse stale paths.
        sbref = _pair_sbref_for_bold(sbref_cands, d.src_nii)
        if sbref:
            _move_sbref_pair(sbref, d.dst_nii, overwrite=overwrite, task_name=task_name)
            # Remove from pool so it cannot be reused for later runs (and cannot crash via stale paths).
            sbref_cands = [p for p in sbref_cands if p != sbref]


# ---------------------------------------------------------------------------
# REST-specific helpers
# ---------------------------------------------------------------------------


def _collect_rest_candidates(ss: SubjectSession, rest_seq: YSeq, src_root: Path) -> List[Path]:
    subj_dir = src_root / ss.sub / (ss.ses or "")
    return sorted(subj_dir.rglob(f"{rest_seq.sequence_id}_*.nii.gz"))


def _cleanup_losers(losers: Iterable[Path]) -> None:
    for lf in losers:
        try:
            jf = lf.with_suffix("").with_suffix(".json")
            if jf.exists():
                jf.unlink()
            lf.unlink()
            log.debug("Deleted leftover REST candidate %s", lf)
        except Exception as exc:
            log.warning("Could not delete %s: %s", lf, exc)


def _process_rest(
    ss: SubjectSession,
    *,
    rest_seq: YSeq,
    src_root: Path,
    dataset_root: Path,
    overwrite: bool,
    vol_filter: Mapping[str, int],
    delete_losers: bool,
) -> None:
    candidates = _collect_rest_candidates(ss, rest_seq, src_root)
    if not candidates:
        log.info("No resting-state NIfTIs for %s %s", ss.sub, ss.ses or "")
        return

    # Winner selection should ignore SBRef
    bold_candidates = [p for p in candidates if not is_sbref_nifti(p)]
    if not bold_candidates:
        log.info("[%s %s] rest – only SBRef candidates found; skipping", ss.sub, ss.ses or "")
        return

    best = max(bold_candidates, key=_rank_nifti)
    dir_tok = _dir_token(best)

    log.info(
        "[%s %s] rest – selected %s (%d vols) as winning run",
        ss.sub,
        ss.ses or "",
        best.name,
        _n_vols(best),
    )

    # FIX: previously referenced an undefined helper `_dir_token_from_name`.
    # Use `_dir_token(Path)` which is already defined and supports JSON fallback.
    bucket = [p for p in candidates if _dir_token(p) == dir_tok] if dir_tok else candidates

    _process_dir(
        bucket,
        dir_token=dir_tok,
        task_name="rest",
        seq=rest_seq,
        ss=ss,
        dataset_root=dataset_root,
        overwrite=overwrite,
        vol_filter=vol_filter,
    )

    if delete_losers:
        losers = [p for p in candidates if p != best]
        if losers:
            log.info(
                "[%s %s] rest – deleting %d loser file(s) from sourcedata/nifti",
                ss.sub,
                ss.ses or "",
                len(losers),
            )
            _cleanup_losers(losers)


# ---------------------------------------------------------------------------
# Subject/session dispatcher (task + rest)
# ---------------------------------------------------------------------------


def _process_subject_session(
    ss: SubjectSession,
    *,
    task_seq: YSeq,
    rest_seq: YSeq,
    src_root: Path,
    dataset_root: Path,
    tasks: list[str],
    include_rest: bool,
    overwrite: bool,
    vol_filter: Mapping[str, int],
    delete_losers: bool,
) -> None:
    task_candidates = sorted(
        (src_root / ss.sub / (ss.ses or "")).rglob(f"{task_seq.sequence_id}*.nii.gz")
    )

    have_task_files = bool(task_candidates)
    if not have_task_files:
        if include_rest and not tasks:
            log.info(
                "No task fMRI NIfTIs for %s %s – continuing with REST-only flow",
                ss.sub,
                ss.ses or "",
            )
        elif tasks:
            log.error("No functional NIfTIs found for %s %s (task search)", ss.sub, ss.ses or "")
        buckets: DefaultDict[str | None, list[Path]] = defaultdict(list)
    else:
        buckets = defaultdict(list)
        for p in task_candidates:
            # SBRef still participates in grouping by task; we filter later.
            buckets[_task_of(p)].append(p)

    if tasks:
        for task_name in tasks:
            key = None if task_name == "task" else task_name.lower()
            paths_for_task = buckets.get(key, [])

            if (
                not paths_for_task
                and key is not None
                and len(tasks) == 1
                and buckets.get(None)
            ):
                paths_for_task = buckets[None]
                log.info(
                    "[%s %s] Using %d unlabeled run(s) for task=%s",
                    ss.sub,
                    ss.ses or "",
                    len(paths_for_task),
                    task_name,
                )
                buckets[None] = []

            _process_task(
                task_name=task_name,
                paths=paths_for_task,
                ss=ss,
                seq=task_seq,
                dataset_root=dataset_root,
                overwrite=overwrite,
                vol_filter=vol_filter,
            )

    if include_rest:
        _process_rest(
            ss,
            rest_seq=rest_seq,
            src_root=src_root,
            dataset_root=dataset_root,
            overwrite=overwrite,
            vol_filter=vol_filter,
            delete_losers=delete_losers,
        )

    # Clear JSON cache between subject/sessions
    clear_meta_cache()


def _process_task(
    task_name: str,
    paths: list[Path],
    *,
    ss: SubjectSession,
    seq: YSeq,
    dataset_root: Path,
    overwrite: bool,
    vol_filter: Mapping[str, int],
) -> None:
    from collections import defaultdict

    dir_buckets: DefaultDict[str | None, list[Path]] = defaultdict(list)

    for p in paths:
        dir_buckets[_dir_token(p)].append(p)

    # Stable ordering: common directions first, None last, unknown labels alphabetical.
    order = {"AP": 0, "PA": 1, "LR": 2, "RL": 3, "SI": 4, "IS": 5}

    def _key(tok: str | None) -> tuple[int, str]:
        if tok is None:
            return (99, "")
        return (order.get(tok, 50), tok)

    for dir_token, bucket in sorted(dir_buckets.items(), key=lambda kv: _key(kv[0])):
        if bucket:
            _process_dir(
                bucket,
                dir_token=dir_token,
                task_name=task_name,
                seq=seq,
                ss=ss,
                dataset_root=dataset_root,
                overwrite=overwrite,
                vol_filter=vol_filter,
            )


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def bidsify_functional(
    *,
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: ConfigSchema,
    overwrite: bool = False,
    tasks: list[str] | None = None,
    include_rest: bool = False,
    vol_filter: Mapping[str, int] | None = None,
    delete_losers: bool = DELETE_LOSERS_DEFAULT,
) -> None:
    tasks = tasks or []
    vol_filter = vol_filter or {}

    task_seq = cfg.modalities["functional"]["task"]
    rest_seq = cfg.modalities["functional"]["rest"]
    src_root = dataset_root / "sourcedata" / "nifti"

    for ss in sessions:
        _process_subject_session(
            ss,
            task_seq=task_seq,
            rest_seq=rest_seq,
            src_root=src_root,
            dataset_root=dataset_root,
            tasks=tasks,
            include_rest=include_rest,
            overwrite=overwrite,
            vol_filter=vol_filter,
            delete_losers=delete_losers,
        )


__all__: list[str] = ["bidsify_functional"]
