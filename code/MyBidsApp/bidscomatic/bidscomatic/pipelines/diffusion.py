"""Move diffusion-weighted NIfTIs from *sourcedata/nifti* into ``sub-*/[ses-*]/dwi/``.

Key points
----------
* Delegates selection heuristics to
  :func:`bidscomatic.pipelines._selection.best_runs`.
* Uses the shared :func:`bidscomatic.pipelines._entities.render_entities`
  helper so filenames never contain doubled prefixes.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Iterable, List, Mapping

from bidscomatic.config.schema import BIDSEntities, ConfigSchema, Sequence as YSeq
from bidscomatic.models import BIDSPath
from bidscomatic.pipelines._selection import best_runs
from bidscomatic.pipelines._entities import render_entities as _render_entities
from bidscomatic.pipelines.types import SubjectSession

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
_EXTS = (".nii.gz", ".bvec", ".bval", ".json")

# --------------------------------------------------------------------------- #
# Tiny helpers                                                                #
# --------------------------------------------------------------------------- #
def _collect(src_root: Path, ss: SubjectSession, seq: YSeq) -> List[Path]:
    """Return every NIfTI whose name contains ``seq.sequence_id``."""
    subj_dir = src_root / ss.sub / (ss.ses or "")
    return sorted(subj_dir.rglob(f"{seq.sequence_id}*.nii.gz"))


def _pair_sidecars(nii: Path) -> List[Path]:
    """Return *nii* plus any existing side-car files in *_EXTS*."""
    base = nii.with_suffix("")  # strip .gz → .nii → bare stem
    paths = [nii]
    for ext in _EXTS[1:]:
        p = base.with_suffix(ext)
        if p.exists():
            paths.append(p)
    return paths


def _sidecar_target(src: Path, dst_nii: Path) -> Path:
    """Return the correct destination path for *src*.

    Args:
        src: Path of the source file (NIfTI or side-car).
        dst_nii: Final path of the ``.nii.gz`` file.

    Returns:
        The destination path for *src* in the BIDS tree.
    """
    if src.suffix == ".gz":  # The NIfTI itself
        return dst_nii

    # Remove .gz then .nii, finally add the side-car suffix.
    return dst_nii.with_suffix("").with_suffix(src.suffix)


def _move(src: Path, dst: Path, *, overwrite: bool) -> None:
    """Move *src* → *dst*, respecting the *overwrite* flag."""
    if dst.exists() and not overwrite:
        log.info("%s exists – skipped", dst.relative_to(dst.anchor))
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    log.info("%s ↳ %s", src.relative_to(src.anchor), dst.relative_to(dst.anchor))


# --------------------------------------------------------------------------- #
# Public entry-point                                                          #
# --------------------------------------------------------------------------- #
def bidsify_diffusion(
    *,
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: ConfigSchema,
    overwrite: bool = False,
    vol_filter: Mapping[str, int] | None = None,
) -> None:
    """Organise DWI data into the BIDS ``dwi/`` directory.

    Args:
        dataset_root: Path to the dataset root.
        sessions: Iterable of subject/session objects.
        cfg: Validated YAML configuration.
        overwrite: Overwrite existing files when ``True``.
        vol_filter: Optional ``{task: vols}`` mapping to restrict selection
            to runs with a specific volume count.
    """
    seq = cfg.modalities["diffusion"]["multi_shell"]
    src_root = dataset_root / "sourcedata" / "nifti"
    vol_filter = vol_filter or {}

    for ss in sessions:
        cands = _collect(src_root, ss, seq)
        if not cands:
            log.info("No DWI NIfTIs for %s %s", ss.sub, ss.ses or "")
            continue

        # ── Phase-encode bucket → pick best run per shell ─────────────────
        buckets: dict[str | None, List[Path]] = {"AP": [], "PA": [], None: []}
        for p in cands:
            if "_AP_" in p.name:
                buckets["AP"].append(p)
            elif "_PA_" in p.name:
                buckets["PA"].append(p)
            else:
                buckets[None].append(p)

        for dir_tok, group in buckets.items():
            if not group:
                continue

            chosen = best_runs(group, wanted_vols=vol_filter.get("dwi"))
            if not chosen:
                log.warning(
                    "[%s %s] DWI dir=%s – nothing matched volume filter",
                    ss.sub,
                    ss.ses or "",
                    dir_tok or "<none>",
                )
                continue

            for src in chosen:
                ents = _render_entities(
                    seq.bids,
                    sub=ss.sub,
                    ses=ss.ses or "",
                    dir=dir_tok or "",
                )
                bp = BIDSPath(root=dataset_root, datatype="dwi", entities=ents)
                dst_nii = bp.path

                for f in _pair_sidecars(src):
                    tgt = _sidecar_target(f, dst_nii)
                    _move(f, tgt, overwrite=overwrite)
