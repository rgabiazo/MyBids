"""
Organises functional BOLD (task and resting-state) NIfTIs found under
``sourcedata/nifti`` into their final BIDS-compatible ``func/`` folders.

The module is intentionally **pure**: it only performs file discovery,
selection, and movement. Heavy lifting such as DICOM → NIfTI conversion,
BIDS validation, or statistical analysis lives elsewhere. This keeps the
code easy to unit-test and re-use in notebooks or other pipelines.

Key behaviours
--------------
* The *run* entity (``run-01`` etc.) is injected **only** when multiple runs
  are transferred for the same subject/session/task/phase-encode bucket.
* Run selection delegates to :func:`bidscomatic.pipelines._selection.best_runs`
  so anatomical, diffusion, and functional logic stays identical.
* REST NIfTIs are handled separately; deletion of the non-selected runs is
  optional through the *delete_losers* flag.
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

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants and regular expressions
# ---------------------------------------------------------------------------
# Patterns for extracting a numeric index from filenames. Ordered by how
# specific they are; the first match wins.
_IDX_PATTERNS = (
    re.compile(r"_(?:AP|PA|LR|RL|SI)_(\d{2,})"),  # rfMRI_AP_17.nii.gz
    re.compile(r"_i(\d{3,})"),                   # *_i0123.nii.gz
    re.compile(r"[^\d](\d{2,})$"),              # *_15.nii.gz (trailing digits)
)

# Placeholder detection – used for stripping empty placeholders cleanly.
_PLACEHOLDER_RE = re.compile(r"\{(?P<key>\w+)(?::[^\}]+)?\}")

# Cheap cache so every JSON is read at most once per invocation.
_TASK_CACHE: dict[Path, str | None] = {}

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
    """Return *task* label derived from the side-car JSON or *None*.

    The helper caches results in :pydata:`_TASK_CACHE` to avoid repeated disk
    access when the same JSON is inspected multiple times.

    Args:
        path: Path to the ``*.nii.gz`` file.

    Returns:
        The lower-cased value of *TaskName* or *None* when missing/invalid.
    """
    if path not in _TASK_CACHE:
        try:
            meta = json.loads(path.with_suffix("").with_suffix(".json").read_text())
            task_val = meta.get("TaskName")
            _TASK_CACHE[path] = task_val.strip().lower() if isinstance(task_val, str) and task_val.strip() else None
        except Exception:
            _TASK_CACHE[path] = None
    return _TASK_CACHE[path]


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
    # The stable key uses the numeric index when available; falls back to mtime.
    return sorted(paths, key=lambda p: (_filename_index(p) or 9_999_999, p.stat().st_mtime))


# ---------------------------------------------------------------------------
# Entity-rendering helpers
# ---------------------------------------------------------------------------

def _strip_pref(text: str, pref: str) -> str:
    """Remove *pref* from *text* if present (case-sensitive)."""
    return text[len(pref):] if isinstance(text, str) and text.startswith(pref) else text


def _remove_unused_placeholders(tmpl: str, tokens: Dict[str, Any]) -> str:
    """Remove placeholders whose corresponding token is empty or *None*."""

    def repl(match: re.Match[str]) -> str:  # noqa: D401 – small inner helper
        """Return an empty string when *match* maps to a blank token."""
        key = match.group("key")
        return "" if tokens.get(key) in {"", None} else match.group(0)

    return _PLACEHOLDER_RE.sub(repl, tmpl)


def _render_entities(tmpl: BIDSEntities, **tokens) -> BIDSEntities:
    """Render a :class:`~bidscomatic.config.schema.BIDSEntities` template.

    Args:
        tmpl: The template directly from *series.yaml* which may include
            placeholders such as ``{run}`` or ``{dir}``.
        **tokens: Concrete substitutions (``run=1`` etc.).

    Returns:
        A new :class:`~bidscomatic.config.schema.BIDSEntities` instance with
        all placeholders resolved where possible.
    """
    # 1. Normalise tokens so duplicate prefixes never occur (sub-sub-001 …).
    clean: Dict[str, Any] = {
        k: _strip_pref(v, f"{k}-") if isinstance(v, str) else v for k, v in tokens.items()
    }

    rendered: Dict[str, Any] = {}
    for field, raw in tmpl.model_dump().items():
        if not isinstance(raw, str):
            # Non-string entities are copied verbatim (usually *None*).
            rendered[field] = raw
            continue

        safe_tmpl = _remove_unused_placeholders(raw, clean)

        # ``str.format`` would raise KeyError when placeholder remains unresolved.
        try:
            rendered[field] = safe_tmpl.format(**clean)
        except (ValueError, KeyError):
            # Gracefully keep the unresolved placeholder unchanged.
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
            # Corrupted JSON is silently ignored; a fresh one is written.
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
    """Handle one subject/session/dir-bucket by moving the chosen runs.

    The function is intentionally chatty: INFO-level breadcrumbs trace the
    selection process so debugging large datasets stays feasible.
    """
    chosen = _best_subset(group, vol_filter.get(task_name))
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


# ---------------------------------------------------------------------------
# REST-specific helpers
# ---------------------------------------------------------------------------

def _collect_rest_candidates(ss: SubjectSession, rest_seq: YSeq, src_root: Path) -> List[Path]:
    """Return every resting-state NIfTI for *ss* matching *rest_seq*."""
    subj_dir = src_root / ss.sub / (ss.ses or "")
    return sorted(subj_dir.rglob(f"{rest_seq.sequence_id}_*.nii.gz"))


def _dir_token_of(fname: str) -> str | None:
    """Infer PE direction token from *fname* (AP/PA) or *None*."""
    if "_AP_" in fname:
        return "AP"
    if "_PA_" in fname:
        return "PA"
    return None


def _cleanup_losers(losers: Iterable[Path]) -> None:
    """Delete loser files and their JSONs; silence errors."""
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
    """Handle resting-state files for one subject/session."""
    candidates = _collect_rest_candidates(ss, rest_seq, src_root)
    if not candidates:
        log.info("No resting-state NIfTIs for %s %s", ss.sub, ss.ses or "")
        return

    best = max(candidates, key=_rank_nifti)
    dir_tok = _dir_token_of(best.name)

    log.info(
        "[%s %s] rest – selected %s (%d vols) as winning run",
        ss.sub,
        ss.ses or "",
        best.name,
        _n_vols(best),
    )

    # 1) Move the winner into BIDS.
    _process_dir(
        [best],
        dir_token=dir_tok,
        task_name="rest",
        seq=rest_seq,
        ss=ss,
        dataset_root=dataset_root,
        overwrite=overwrite,
        vol_filter=vol_filter,
    )

    # 2) Optionally delete losers.
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
    """Entry-point for processing one *SubjectSession*."""
    task_candidates = sorted(
        (src_root / ss.sub / (ss.ses or "")).rglob(f"{task_seq.sequence_id}*.nii.gz")
    )

    have_task_files = bool(task_candidates)
    if not have_task_files:
        # Decide whether skipping is fatal or expected.
        if include_rest and not tasks:
            log.info(
                "No task fMRI NIfTIs for %s %s – continuing with REST-only flow",
                ss.sub,
                ss.ses or "",
            )
        elif tasks:
            log.error("No functional NIfTIs found for %s %s (task search)", ss.sub, ss.ses or "")
        # Prepare empty buckets so REST can still run.
        buckets: DefaultDict[str | None, list[Path]] = defaultdict(list)
    else:
        # Group task files by TaskName (None = unlabeled).
        buckets = defaultdict(list)
        for p in task_candidates:
            buckets[_task_of(p)].append(p)

    # --------------------------- task runs --------------------------------
    if tasks:
        for task_name in tasks:
            key = None if task_name == "task" else task_name.lower()
            paths_for_task = buckets.get(key, [])

            # Tolerate unlabeled runs when exactly one task requested.
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
                buckets[None] = []  # prevent duplicate processing later

            _process_task(
                task_name=task_name,
                paths=paths_for_task,
                ss=ss,
                seq=task_seq,
                dataset_root=dataset_root,
                overwrite=overwrite,
                vol_filter=vol_filter,
            )

    # --------------------------- REST runs --------------------------------
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

    # Reset JSON cache for next subject/session.
    _TASK_CACHE.clear()


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
    """Process one *task* (e.g. *nback*) for a specific subject/session."""
    # Bucket paths by PE direction so *best_runs()* is applied per bucket.
    dir_buckets: Dict[str | None, list[Path]] = {d.value: [] for d in PhaseDir}
    dir_buckets[None] = []

    for p in paths:
        if "_AP_" in p.name:
            dir_buckets[PhaseDir.AP.value].append(p)
        elif "_PA_" in p.name:
            dir_buckets[PhaseDir.PA.value].append(p)
        else:
            dir_buckets[None].append(p)

    for dir_token, bucket in dir_buckets.items():
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
# Public entry-point (called by CLI and tests)
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
    """Organise functional NIfTIs into their BIDS *func/* folders.

    Args:
        dataset_root: Path to the dataset root containing ``dataset_description.json``.
        sessions: Iterable of :class:`~bidscomatic.pipelines.types.SubjectSession`.
        cfg: Parsed *series.yaml* configuration.
        overwrite: Replace existing files when *True*.
        tasks: Explicit task names (e.g. ``["nback", "stroop"]``). ``None``
            means *task* sub-flag was omitted.
        include_rest: Process resting-state runs as well.
        vol_filter: Optional mapping *task → expected volume count*.
        delete_losers: When *True*, delete non-selected REST runs from
            *sourcedata* (legacy behaviour).
    """
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
