"""Move anatomical NIfTIs from *sourcedata/nifti* into ``sub-*/[ses-*/]anat/``.

Key points
----------
* Keeps cross-pipeline consistency by delegating common ranking logic to
  :func:`bidscomatic.pipelines._selection.best_runs`.
* Restores the original anatomical tie-break so the file with the highest
  ``_vNav_<NN>`` (or, when absent, the highest SeriesNumber) is preferred.
"""
from __future__ import annotations

import logging
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from bidscomatic.config.schema import (
    BIDSEntities,
    ConfigSchema,
    Sequence as YamlSequence,
)
from bidscomatic.models import BIDSPath
from bidscomatic.pipelines._selection import best_runs  # shared helper
from bidscomatic.pipelines.types import SubjectSession

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Helper – name normalisation and subtype alias table
# ─────────────────────────────────────────────────────────────────────────────
_NORMALISE_RE = re.compile(r"[\s_\-]+")


def _normalise(text: str) -> str:
    """Return *text* lower-cased, ASCII-only, with separators collapsed to “-”."""
    txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _NORMALISE_RE.sub("-", txt.strip().lower())


def build_subtype_aliases(cfg_anat: Mapping[str, YamlSequence]) -> dict[str, str]:
    """Return a map ``{<cli token>: <canonical YAML key>}``.

    The mapping allows flexible command-line spelling, e.g. ``t1`` →
    ``T1w`` or ``hippocamp`` → ``Hippocampus``.
    """
    out: dict[str, str] = {}
    for key, seq in cfg_anat.items():
        slug = _normalise(key)
        out[slug] = key
        out[slug.replace("t1", "t1w")] = key
        out[slug.replace("hippocamp", "hippocampus")] = key
        out[_normalise(seq.sequence_id)] = key  # e.g. “HighResHippocampus”
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Discovery and ranking helpers
# ─────────────────────────────────────────────────────────────────────────────
_VNAV = re.compile(r"_vNav_(\d+)", re.I)
_SER = re.compile(r"_i(\d{3,})")
_NII_GLOB = "{}*.nii.gz"  # filled with sequence_id from YAML


def _rank(fname: Path) -> tuple[int, int]:
    """Return ``(vNav_number, series_number)`` ranking tuple for *fname*."""
    vnav = int(_VNAV.search(fname.stem).group(1)) if _VNAV.search(fname.stem) else 0
    ser = int(_SER.search(fname.stem).group(1)) if _SER.search(fname.stem) else 0
    return vnav, ser


def _find(src_root: Path, ss: SubjectSession, seq: YamlSequence) -> list[Path]:
    """Return every NIfTI under *src_root* that matches *seq.sequence_id*."""
    subj_dir = src_root / ss.sub / (ss.ses or "")
    return sorted(subj_dir.rglob(_NII_GLOB.format(seq.sequence_id)))


# ─────────────────────────────────────────────────────────────────────────────
# JSON side-car pairing
# ─────────────────────────────────────────────────────────────────────────────
def _with_json(nifti: Path) -> Sequence[Path]:
    """Return the NIfTI plus its JSON side-car when present."""
    flat = nifti.with_suffix("").with_suffix(".json")  # foo.nii.json
    gz   = nifti.with_suffix(".json")                  # foo.json
    return (nifti, flat) if flat.exists() else (nifti, gz) if gz.exists() else (nifti,)


# ─────────────────────────────────────────────────────────────────────────────
# Entity rendering helpers
# ─────────────────────────────────────────────────────────────────────────────
def _strip_pref(text: str, pref: str) -> str:
    """Remove *pref* from the start of *text*."""
    return text[len(pref):] if text.startswith(pref) else text


def _render_entities(
    tmpl: BIDSEntities, *, sub: str, ses: str | None, label: str
) -> BIDSEntities:
    """Render *tmpl* using the provided subject, session, and label tokens."""
    tokens = {
        "sub": _strip_pref(sub, "sub-"),
        "ses": _strip_pref(ses, "ses-") if ses else "",
        "label": label,
    }
    data: dict[str, str] = {}
    for field, value in tmpl.model_dump().items():
        data[field] = value.format(**tokens) if isinstance(value, str) else value
    return BIDSEntities(**data)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────
def bidsify_anatomical(
    *,
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: ConfigSchema,
    subtypes: Iterable[str],
    overwrite: bool = False,
) -> None:
    """Move anatomical files into their final BIDS layout.

    Args:
        dataset_root: Path to the dataset root (folder containing
            *dataset_description.json*).
        sessions: Iterable of subject/session objects to process.
        cfg: Parsed YAML configuration.
        subtypes: CLI tokens indicating which anatomical sequences to move
            (e.g. ``t1w``, ``hippocampus``). Tokens are resolved against
            :func:`build_subtype_aliases`.
        overwrite: Overwrite existing target files when ``True``.
    """
    ana_cfg = cfg.modalities["anatomical"]
    aliases = build_subtype_aliases(ana_cfg)
    src_root = dataset_root / "sourcedata" / "nifti"

    # Translate CLI tokens → canonical YAML keys.
    wanted: list[str] = []
    for tok in subtypes:
        key = aliases.get(_normalise(tok))
        if key:
            wanted.append(key)
        else:
            log.warning("Unknown anatomical subtype ignored: %s", tok)
    if not wanted:
        log.info("Nothing to do – no valid subtypes requested.")
        return

    # Iterate over subject/session × subtype.
    for ss in sessions:
        for name in wanted:
            seq = ana_cfg[name]
            cands = _find(src_root, ss, seq)

            # 1) Generic filter (removes duplicates, wrong volume-count, etc.).
            prelim = best_runs(cands)
            # 2) Anatomical tie-break – prefer higher vNav / SeriesNumber.
            cand = max(prelim, key=_rank, default=None)

            if not cand:
                log.warning("No %s candidate for %s %s", name, ss.sub, ss.ses or "")
                continue

            log.info(
                "Picked %s (rank=%s) for %s %s",
                cand.name,
                _rank(cand),
                ss.sub,
                ss.ses or "",
            )

            anat_dir = dataset_root / ss.sub / (ss.ses or "") / "anat"
            anat_dir.mkdir(parents=True, exist_ok=True)

            ents = _render_entities(
                seq.bids, sub=ss.sub, ses=ss.ses, label=(seq.label or name)
            )
            filename = BIDSPath(
                root=Path("/dev/null"), datatype="anat", entities=ents
            ).filename

            dst_nii   = anat_dir / filename
            dst_json  = dst_nii.with_suffix("").with_suffix(".json")

            if dst_nii.exists() and not overwrite:
                log.info("%s exists – skipped (use --overwrite)", dst_nii)
                continue

            # Move the chosen NIfTI and its JSON side-car.
            for src in _with_json(cand):
                target = dst_nii if src.suffix == ".gz" else dst_json
                if target.exists():
                    target.unlink()
                shutil.move(str(src), target)
                log.info(
                    "%s ↳ %s",
                    src.relative_to(dataset_root),
                    target.relative_to(dataset_root),
                )


__all__ = ["bidsify_anatomical", "build_subtype_aliases", "_normalise"]
