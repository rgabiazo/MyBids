"""Populate ``fmap/…_epi.nii.gz`` when functional runs exist for one phase direction.

Selection rules
---------------
1. Prefer runs with more volumes (rare for EPI field-maps).
2. Break ties using the SeriesNumber encoded in the filename.
3. If still tied, prefer newer modification time.
4. As a last resort, prefer larger file size.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import Iterable, List

import nibabel as nib

from bidscomatic.config.schema import BIDSEntities, ConfigSchema, Sequence as YSeq
from bidscomatic.models import BIDSPath
from bidscomatic.pipelines.types import SubjectSession

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Regular expressions
# ─────────────────────────────────────────────────────────────────────────────
_DIR_RE = re.compile(r"_dir-(AP|PA|LR|RL|SI)[_.]", re.I)
_SER_RE = re.compile(r"(?:[_-]i|[_-](?:AP|PA|LR|RL|SI)[_-])(\d{2,})")

_OPPOSITE = {
    "AP": "PA",
    "PA": "AP",
    "LR": "RL",
    "RL": "LR",
    # SI has no strict opposite
}

# ─────────────────────────────────────────────────────────────────────────────
# Single-file helpers
# ─────────────────────────────────────────────────────────────────────────────
def _dir_of_bold(name: str) -> str | None:
    """Return the phase-encode direction token embedded in *name*."""
    match = _DIR_RE.search(name)
    return match.group(1) if match else None


def _n_vols(p: Path) -> int:
    """Return the number of 4-D volumes in *p* (fallback to 1 for 3-D)."""
    img = nib.load(p)
    return img.shape[3] if img.ndim == 4 else 1


def _series_index(p: Path) -> int:
    """Extract SeriesNumber from *p*; returns ``-1`` when absent."""
    match = _SER_RE.search(p.stem)
    return int(match.group(1)) if match else -1

# ─────────────────────────────────────────────────────────────────────────────
# Minimal entity renderer (inline copy to avoid an import cycle)
# ─────────────────────────────────────────────────────────────────────────────
def _strip_pref(text: str, pref: str) -> str:
    """Remove *pref* from the start of *text*."""
    return text[len(pref):] if isinstance(text, str) and text.startswith(pref) else text


def _render_entities(tmpl: BIDSEntities, **tokens) -> BIDSEntities:
    """Render *tmpl* with *tokens* while stripping doubled prefixes."""
    rendered: dict[str, str] = {}
    for key, raw in tmpl.model_dump().items():
        if not isinstance(raw, str):
            rendered[key] = raw
            continue
        rendered[key] = raw.format(**{t: _strip_pref(v, f"{t}-") for t, v in tokens.items()})
    return BIDSEntities(**rendered)

# ─────────────────────────────────────────────────────────────────────────────
# Directory-level helpers
# ─────────────────────────────────────────────────────────────────────────────
def _bolds_in_bids(root: Path, ss: SubjectSession) -> List[Path]:
    """Return every ``*_bold.nii.gz`` in the subject/session FUNC folder."""
    func_dir = root / ss.sub / (ss.ses or "") / "func"
    return sorted(func_dir.glob("*_bold.nii.gz")) if func_dir.exists() else []


def _missing_dirs(bolds: List[Path]) -> set[str]:
    """Return PE directions that are present only on one side."""
    present = {_dir_of_bold(p.name) for p in bolds if _dir_of_bold(p.name)}
    wanted = {_OPPOSITE[d] for d in present if d in _OPPOSITE}
    return wanted - present


def _candidate_niftis(
    src_root: Path,
    ss: SubjectSession,
    seq: YSeq,
    wanted_dir: str,
) -> List[Path]:
    """Return NIfTIs matching *seq.sequence_id* and *wanted_dir*."""
    subj_dir = src_root / ss.sub / (ss.ses or "")
    pattern = f"{seq.sequence_id}*{wanted_dir}_*.nii.gz"
    return sorted(subj_dir.rglob(pattern))

# ─────────────────────────────────────────────────────────────────────────────
# Tie-break helper
# ─────────────────────────────────────────────────────────────────────────────
def _pick_best(cands: List[Path]) -> Path | None:
    """Return the best candidate from *cands* following the documented rules."""
    if not cands:
        return None

    # Rule 1 – most volumes
    vols = {p: _n_vols(p) for p in cands}
    best_vol = max(vols.values())
    tied = [p for p, v in vols.items() if v == best_vol]
    if len(tied) == 1:
        return tied[0]

    # Rule 2 – highest SeriesNumber
    best_series = max(_series_index(p) for p in tied)
    tied = [p for p in tied if _series_index(p) == best_series]
    if len(tied) == 1:
        return tied[0]

    # Rule 3 – newest modification time
    tied.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(tied) > 1:
        # Rule 4 – largest file size
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
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────
def bidsify_fieldmaps(
    *,
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: ConfigSchema,
    overwrite: bool = False,
) -> None:
    """Populate *epi* field-maps for missing opposite PE directions."""
    seq: YSeq = cfg.modalities["functional"]["fieldmap_epi"]
    src_root = dataset_root / "sourcedata" / "nifti"

    for ss in sessions:
        bolds = _bolds_in_bids(dataset_root, ss) or [
            # Fallback: sourcedata/nifti when --epi runs standalone
            p
            for p in (src_root / ss.sub / (ss.ses or "")).rglob(f"{seq.sequence_id}*AP*.nii.gz")
        ]
        if not bolds:
            log.debug("No BOLD files for %s %s – skipping", ss.sub, ss.ses or "")
            continue

        missing = _missing_dirs(bolds)
        if not missing:
            log.debug("%s %s already has both PE dirs", ss.sub, ss.ses or "")
            continue

        for dir_tok in missing:
            cands = _candidate_niftis(src_root, ss, seq, dir_tok)
            best = _pick_best(cands)
            if not best:
                log.warning(
                    "[%s %s] Needed dir-%s field-map but none found",
                    ss.sub,
                    ss.ses or "",
                    dir_tok,
                )
                continue

            ents = _render_entities(seq.bids, sub=ss.sub, ses=ss.ses or "", dir=dir_tok)
            bp = BIDSPath(root=dataset_root, datatype="fmap", entities=ents)

            _move_pair(best, bp.path, overwrite=overwrite)
            _move_pair(
                best.with_suffix("").with_suffix(".json"),
                bp.path.with_suffix("").with_suffix(".json"),
                overwrite=overwrite,
            )

__all__ = ["bidsify_fieldmaps"]
