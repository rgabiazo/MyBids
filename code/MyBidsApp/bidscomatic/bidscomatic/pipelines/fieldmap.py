"""Populate ``fmap/…_epi.nii.gz`` when functional runs exist for one phase direction.

Selection rules
---------------
1. Prefer runs with more volumes (rare for EPI field-maps).
2. Break ties using the SeriesNumber encoded in the filename.
3. If still tied, prefer newer modification time.
4. As a last resort, prefer larger file size.

Best-practice extras
--------------------
* Can write/update ``IntendedFor`` in the destination JSON to point at the
  subject/session functional file(s) expected to use this field-map.
* Optional ``intended_rel`` mode writes IntendedFor entries relative to the
  subject directory (e.g. ``ses-01/func/...``), and can harmonize
  ``TotalReadoutTime`` to match the intended targets when consistent.

Safety rule (SBRef)
-------------------
SBRef (single-band reference) images are *not* field-maps. Some exports name
SBRef volumes similarly to short EPI acquisitions (e.g. ``rfMRI_PA_25``) which
can cause accidental misclassification. This module therefore excludes files
whose sidecar JSON indicates SBRef (e.g. ``ImageComments: "Single-band reference"``
or ``SeriesDescription`` contains ``SBRef``).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Iterable, List

import nibabel as nib

from bidscomatic.config.schema import ConfigSchema, Sequence as YSeq
from bidscomatic.models import BIDSPath
from bidscomatic.pipelines._entities import render_entities as _render_entities
from bidscomatic.pipelines._meta import clear_meta_cache, is_sbref_nifti
from bidscomatic.pipelines.types import SubjectSession

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Regular expressions
# ─────────────────────────────────────────────────────────────────────────────
_DIR_RE = re.compile(r"_dir-(AP|PA|LR|RL|SI)(?=[_.])", re.I)
_SER_RE = re.compile(r"(?:[_-]i|[_-](?:AP|PA|LR|RL|SI)[_-])(\d{2,})", re.I)

_OPPOSITE = {
    "AP": "PA",
    "PA": "AP",
    "LR": "RL",
    "RL": "LR",
    # SI/IS are uncommon here and may not have strict opposites for all datasets.
}


# ─────────────────────────────────────────────────────────────────────────────
# JSON helpers (robust round-trip)
# ─────────────────────────────────────────────────────────────────────────────
def _json_sidecar(nifti: Path) -> Path:
    """Return the JSON sidecar path for a NIfTI image (.nii or .nii.gz)."""
    if nifti.name.endswith(".nii.gz"):
        return nifti.with_suffix("").with_suffix(".json")
    return nifti.with_suffix(".json")


def _read_json_safe(path: Path) -> dict:
    """Read JSON from *path*; return {} on missing/empty/invalid."""
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text() or "{}") or {}
    except Exception:
        return {}


def _coerce_float(v) -> float | None:
    """Try to coerce *v* to float, else None."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _total_readout_time_of(nifti: Path) -> float | None:
    """Return TotalReadoutTime from nifti's sidecar JSON (if present)."""
    meta = _read_json_safe(_json_sidecar(nifti))
    return _coerce_float(meta.get("TotalReadoutTime"))


def _write_json(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Direction helpers
# ─────────────────────────────────────────────────────────────────────────────
def _dir_of_name(name: str) -> str | None:
    """Return the phase-encode direction token embedded in *name*."""
    if (m := _DIR_RE.search(name)):
        return m.group(1).upper()
    up = name.upper()
    if "_AP_" in up:
        return "AP"
    if "_PA_" in up:
        return "PA"
    if "_LR_" in up:
        return "LR"
    if "_RL_" in up:
        return "RL"
    if "_SI_" in up:
        return "SI"
    return None


def _n_vols(p: Path) -> int:
    """Return the number of 4-D volumes in *p* (fallback to 1 for 3-D)."""
    img = nib.load(p)
    return img.shape[3] if img.ndim == 4 else 1


def _series_index(p: Path) -> int:
    """Extract SeriesNumber from *p*; returns ``-1`` when absent."""
    match = _SER_RE.search(p.stem)
    return int(match.group(1)) if match else -1


# ─────────────────────────────────────────────────────────────────────────────
# Discovery helpers
# ─────────────────────────────────────────────────────────────────────────────
def _bolds_in_bids(root: Path, ss: SubjectSession) -> List[Path]:
    """Return every ``*_bold.nii[.gz]`` in the subject/session FUNC folder."""
    func_dir = root / ss.sub / (ss.ses or "") / "func"
    if not func_dir.exists():
        return []
    out: list[Path] = []
    out.extend(func_dir.glob("*_bold.nii.gz"))
    out.extend(func_dir.glob("*_bold.nii"))
    return sorted({p for p in out if p.is_file()})


def _func_targets_in_bids(root: Path, ss: SubjectSession, *, include_sbref: bool) -> List[Path]:
    """Return func targets (BOLD and optionally SBRef) inside the BIDS func/ dir."""
    func_dir = root / ss.sub / (ss.ses or "") / "func"
    if not func_dir.exists():
        return []

    out: list[Path] = []
    for pat in ("*_bold.nii.gz", "*_bold.nii"):
        out.extend(func_dir.glob(pat))
    if include_sbref:
        for pat in ("*_sbref.nii.gz", "*_sbref.nii"):
            out.extend(func_dir.glob(pat))

    return sorted({p for p in out if p.is_file()})


def _bolds_in_sourcedata(src_root: Path, ss: SubjectSession, cfg: ConfigSchema) -> List[Path]:
    """Return likely functional BOLD candidates in sourcedata (excluding SBRef)."""
    subj_dir = src_root / ss.sub / (ss.ses or "")
    task_id = cfg.modalities["functional"]["task"].sequence_id
    rest_id = cfg.modalities["functional"]["rest"].sequence_id

    cands = sorted(subj_dir.rglob(f"{task_id}*.nii.gz")) + sorted(
        subj_dir.rglob(f"{rest_id}*.nii.gz")
    )
    return [p for p in cands if not is_sbref_nifti(p)]


def _missing_dirs(bolds: List[Path]) -> set[str]:
    """Return PE directions that are present only on one side."""
    present = {_dir_of_name(p.name) for p in bolds if _dir_of_name(p.name)}
    wanted = {_OPPOSITE[d] for d in present if d in _OPPOSITE}
    return wanted - present


def _candidate_niftis(
    src_root: Path,
    ss: SubjectSession,
    seq: YSeq,
    wanted_dir: str,
) -> List[Path]:
    """Return candidate EPI field-maps matching *seq.sequence_id* and *wanted_dir*.

    Preference is given to "strict" matches such as ``rfMRI_PA_25.nii.gz``.
    A broader fallback is only used when strict matching yields nothing and
    excludes obvious task/rest BOLD names.
    """
    subj_dir = src_root / ss.sub / (ss.ses or "")

    strict = sorted(subj_dir.rglob(f"{seq.sequence_id}_{wanted_dir}_*.nii.gz"))
    if strict:
        return strict

    broad = sorted(subj_dir.rglob(f"{seq.sequence_id}*{wanted_dir}_*.nii.gz"))
    out: list[Path] = []
    for p in broad:
        up = p.name.upper()
        if "_TASK_" in up or "_REST_" in up:
            continue
        out.append(p)
    return out


def _pick_best(cands: List[Path]) -> Path | None:
    """Return the best candidate from *cands* following the documented rules."""
    if not cands:
        return None

    vols = {p: _n_vols(p) for p in cands}
    best_vol = max(vols.values())
    tied = [p for p, v in vols.items() if v == best_vol]
    if len(tied) == 1:
        return tied[0]

    best_series = max(_series_index(p) for p in tied)
    tied = [p for p in tied if _series_index(p) == best_series]
    if len(tied) == 1:
        return tied[0]

    tied.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(tied) > 1:
        tied.sort(key=lambda p: p.stat().st_size, reverse=True)
    return tied[0]


def _move_pair(src: Path, dst: Path, *, overwrite: bool = False) -> None:
    """Move *src* → *dst* with optional overwrite."""
    if dst.exists() and not overwrite:
        log.info("%s exists – skipped", dst.relative_to(dst.anchor))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    log.info("%s ↳ %s", src.relative_to(src.anchor), dst.relative_to(dst.anchor))


# ─────────────────────────────────────────────────────────────────────────────
# IntendedFor helpers
# ─────────────────────────────────────────────────────────────────────────────
def _format_intended_for(dataset_root: Path, ss: SubjectSession, target: Path, *, relative_to_subject: bool) -> str:
    """Format IntendedFor entry as POSIX path.

    If relative_to_subject=True, try to write paths relative to <root>/<sub-XXX>/,
    which yields values like:
      * ses-01/func/sub-XXX_ses-01_task-..._bold.nii.gz
      * func/sub-XXX_task-..._bold.nii.gz  (when no session)
    """
    if relative_to_subject:
        try:
            rel = target.relative_to(dataset_root / ss.sub)
        except ValueError:
            rel = target.relative_to(dataset_root)
    else:
        rel = target.relative_to(dataset_root)
    return rel.as_posix()


def _update_epi_fmap_intended_for(
    *,
    dataset_root: Path,
    ss: SubjectSession,
    fmap_nii: Path,
    fmap_dir: str,
    include_sbref: bool,
    intended_rel: bool,
) -> None:
    """Update one fmap/*_epi.json IntendedFor (+ TRT harmonization)."""
    opp = _OPPOSITE.get(fmap_dir)
    if not opp:
        log.debug("[%s %s] fmap dir-%s has no declared opposite; skipping IntendedFor update", ss.sub, ss.ses or "", fmap_dir)
        return

    targets = _func_targets_in_bids(dataset_root, ss, include_sbref=include_sbref)
    if not targets:
        log.debug("[%s %s] no func targets found; skipping IntendedFor update", ss.sub, ss.ses or "")
        return

    intended_targets = [t for t in targets if _dir_of_name(t.name) == opp]
    if not intended_targets:
        log.info(
            "[%s %s] fmap dir-%s: no func targets with opposite dir-%s; leaving IntendedFor unchanged",
            ss.sub,
            ss.ses or "",
            fmap_dir,
            opp,
        )
        return

    intended = [
        _format_intended_for(dataset_root, ss, t, relative_to_subject=intended_rel)
        for t in intended_targets
    ]
    intended = sorted(set(intended))

    # Determine TRT from intended targets (if consistent)
    trts = {round(v, 7) for t in intended_targets if (v := _total_readout_time_of(t)) is not None}
    target_trt = None
    if len(trts) == 1:
        target_trt = next(iter(trts))
    elif len(trts) > 1:
        log.error(
            "[%s %s] inconsistent TotalReadoutTime across intended targets for dir-%s: %s (not updating TRT)",
            ss.sub,
            ss.ses or "",
            fmap_dir,
            sorted(trts),
        )

    fmap_json = _json_sidecar(fmap_nii)
    meta = _read_json_safe(fmap_json)

    meta["IntendedFor"] = intended

    # Harmonize TRT if we have a consistent target TRT
    if target_trt is not None:
        cur_trt = _coerce_float(meta.get("TotalReadoutTime"))
        if cur_trt is None:
            meta["TotalReadoutTime"] = float(target_trt)
            log.info(
                "[%s %s] set TotalReadoutTime=%s in %s",
                ss.sub,
                ss.ses or "",
                target_trt,
                fmap_json.name,
            )
        elif round(cur_trt, 7) != round(target_trt, 7):
            meta["TotalReadoutTime"] = float(target_trt)
            log.warning(
                "[%s %s] TotalReadoutTime mismatch in %s (had=%s, targets=%s) → updated",
                ss.sub,
                ss.ses or "",
                fmap_json.name,
                cur_trt,
                target_trt,
            )

    _write_json(fmap_json, meta)
    log.info(
        "[%s %s] updated IntendedFor (%d target(s)) in %s",
        ss.sub,
        ss.ses or "",
        len(intended),
        fmap_json.relative_to(dataset_root),
    )


def _update_intended_for_in_session(
    dataset_root: Path,
    ss: SubjectSession,
    *,
    include_sbref: bool,
    intended_rel: bool,
) -> None:
    """Update IntendedFor for all EPI fieldmaps in this subject/session."""
    fmap_dir = dataset_root / ss.sub / (ss.ses or "") / "fmap"
    if not fmap_dir.exists():
        return

    fmap_files: list[Path] = []
    fmap_files.extend(fmap_dir.glob("*_epi.nii.gz"))
    fmap_files.extend(fmap_dir.glob("*_epi.nii"))
    fmap_files = sorted({p for p in fmap_files if p.is_file()})

    for fmap_nii in fmap_files:
        d = _dir_of_name(fmap_nii.name)
        if not d:
            continue
        _update_epi_fmap_intended_for(
            dataset_root=dataset_root,
            ss=ss,
            fmap_nii=fmap_nii,
            fmap_dir=d,
            include_sbref=include_sbref,
            intended_rel=intended_rel,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────
def bidsify_fieldmaps(
    *,
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: ConfigSchema,
    overwrite: bool = False,
    intended_rel: bool = False,
) -> None:
    """Populate *epi* field-maps for missing opposite PE directions.

    Args:
        dataset_root: Dataset root.
        sessions: Subject/session objects.
        cfg: Loaded configuration.
        overwrite: Overwrite existing targets when True.
        intended_rel: When True, update IntendedFor in fmap/*_epi.json using
            subject-relative paths and harmonize TotalReadoutTime when consistent.
            This update happens even if no new fieldmap was moved (so it can be
            used to refresh metadata after re-running other steps).
    """
    seq: YSeq = cfg.modalities["functional"]["fieldmap_epi"]
    src_root = dataset_root / "sourcedata" / "nifti"

    for ss in sessions:
        bolds = _bolds_in_bids(dataset_root, ss)
        if not bolds:
            bolds = _bolds_in_sourcedata(src_root, ss, cfg)

        if not bolds:
            log.debug("No BOLD files for %s %s – skipping", ss.sub, ss.ses or "")
            # Still allow IntendedFor updates if requested (may exist from prior runs)
            if intended_rel:
                _update_intended_for_in_session(
                    dataset_root, ss, include_sbref=True, intended_rel=True
                )
            clear_meta_cache()
            continue

        missing = _missing_dirs(bolds)

        # If we need to move missing opposite-phase EPIs -------------------
        for dir_tok in sorted(missing):
            cands = _candidate_niftis(src_root, ss, seq, dir_tok)
            cands = [p for p in cands if not is_sbref_nifti(p)]
            if not cands:
                log.warning(
                    "[%s %s] Needed dir-%s field-map but none found (after SBRef filter)",
                    ss.sub,
                    ss.ses or "",
                    dir_tok,
                )
                continue

            best = _pick_best(cands)
            if not best:
                continue

            ents = _render_entities(seq.bids, sub=ss.sub, ses=ss.ses or "", dir=dir_tok)
            bp = BIDSPath(root=dataset_root, datatype="fmap", entities=ents)

            _move_pair(best, bp.path, overwrite=overwrite)

            src_json = _json_sidecar(best)
            dst_json = _json_sidecar(bp.path)
            if src_json.exists():
                _move_pair(src_json, dst_json, overwrite=overwrite)
            else:
                # Conservative: create minimal JSON if missing (rare with dcm2niix)
                _write_json(dst_json, {})

        # Optional: refresh IntendedFor/TRT for any epi fieldmaps -----------
        if intended_rel:
            _update_intended_for_in_session(
                dataset_root, ss, include_sbref=True, intended_rel=True
            )

        clear_meta_cache()


__all__ = ["bidsify_fieldmaps"]
