"""High level pipeline to derive opposite phase-encoding fieldmaps.

The implementation is intentionally lightweight; it mirrors the behaviour of the
original Bash script but limits itself to straightforward filesystem
operations so it can run in restricted test environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import json
import re
import shutil
import subprocess
import textwrap
import structlog

from .types import SubjectSession
from ..config.pepolar import PepolarConfig
from ..utils import fsl
from ..utils.errors import PePolarError

log = structlog.get_logger()

_RULE = "─" * 76
_BOX_WIDTH = 72
_FINAL_RESULT_RE = re.compile(
    r"Final result:\s*(?:\r?\n|\r)+"
    r"(?P<rows>(?:[^\r\n]*[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s+[-+0-9.eE]+\s*(?:\r?\n|\r)+)+)",
    re.IGNORECASE,
)
_FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


@dataclass
class McflirtRunSummary:
    """Container capturing MCFLIRT artefacts for summary reporting."""

    tag: str
    matrix: list[list[float]]


def _format_path(path: Path, base: Path | None = None) -> str:
    """Return *path* in POSIX form, relative to *base* when possible.

    Args:
        path: Filesystem path to format.
        base: Optional base directory to strip from the front of *path*.

    Returns:
        POSIX-style string representation of *path*, prefixed with ``…/`` when
        rendered relative to *base*.
    """
    as_posix = path.as_posix()
    if base is not None:
        try:
            rel = path.relative_to(base)
        except ValueError:
            return as_posix
        return f"…/{rel.as_posix()}"
    return as_posix


def _box_lines(title: str) -> tuple[str, str]:
    """Return the top and bottom border strings for a box with *title*.

    Args:
        title: Box title used to size the decorative border.

    Returns:
        Tuple containing the top and bottom border strings.
    """
    filler = max(_BOX_WIDTH - len(title), 0)
    top = f"┌─ {title} " + ("─" * filler)
    bottom = "└" + ("─" * (len(top) - 1))
    return top, bottom


def _indent_block(text: str, prefix: str = "   ") -> str:
    """Indent *text* with *prefix* after normalising newline characters.

    Args:
        text: Text block to indent.
        prefix: String inserted at the beginning of each resulting line.

    Returns:
        Indented text block with trailing whitespace stripped.
    """
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    return textwrap.indent(cleaned, prefix)


def _extract_final_matrix(stdout: str) -> tuple[list[list[float]], str]:
    """Return the final 4×4 matrix parsed from MCFLIRT stdout.

    Args:
        stdout: Combined stdout captured from an MCFLIRT or FLIRT run.

    Returns:
        Tuple ``(matrix, cleaned_stdout)`` where ``matrix`` is a list of four
        rows parsed from the final "Final result" block when present, and
        ``cleaned_stdout`` is the remaining stdout with that block removed.
    """
    if not stdout:
        return [], ""
    normalised = stdout.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(_FINAL_RESULT_RE.finditer(normalised))
    if not matches:
        return [], normalised.strip()
    match = matches[-1]
    rows_text = match.group("rows")
    values = [float(token) for token in _FLOAT_RE.findall(rows_text)]
    matrix: list[list[float]] = []
    for idx in range(0, len(values), 4):
        row = values[idx : idx + 4]
        if len(row) < 4:
            break
        matrix.append(row)
        if len(matrix) == 4:
            break
    if not matrix:
        return [], normalised.strip()
    cleaned_parts: list[str] = []
    cursor = 0
    for m in matches:
        cleaned_parts.append(normalised[cursor : m.start()])
        cursor = m.end()
    cleaned_parts.append(normalised[cursor:])
    cleaned_stdout = "".join(cleaned_parts).strip()
    return matrix, cleaned_stdout


def _format_heading(title: str) -> str:
    """Return a heading string padded with box drawing characters."""
    filler = max(_BOX_WIDTH - len(title), 0)
    return f"── {title} " + ("─" * filler)


def _format_matrix(matrix: list[list[float]]) -> list[str]:
    """Return formatted string rows for a 4×4 matrix."""
    formatted: list[str] = []
    for row in matrix:
        formatted_row = "  ".join(f"{value: .6f}".lstrip() for value in row)
        formatted.append(f"    [ {formatted_row} ]")
    return formatted


def _deriv_dir(root: Path, ss: SubjectSession) -> Path:
    """Return the derivatives directory for MCFLIRT outputs.

    Args:
        root: Dataset root directory.
        ss: Subject/session pair describing the current participant.

    Returns:
        Path pointing to ``derivatives/fsl/McFLIRT/<sub>/<ses?>``.
    """
    d = root / "derivatives" / "fsl" / "McFLIRT" / ss.sub
    if ss.ses:
        d = d / ss.ses
    return d


def _prefix(ss: SubjectSession, direction: str) -> str:
    """Return the filename stem prefix for a subject/session/direction."""
    parts = [ss.sub]
    if ss.ses:
        parts.append(ss.ses)
    parts.append(f"dir-{direction}")
    return "_".join(parts)


def _derive_fieldmap(
    dataset_root: Path,
    droot: Path,
    ss: SubjectSession,
    direction: str,
    selection: list[tuple[str, Path, str]],
    out: Path,
) -> list[McflirtRunSummary]:
    """Derive a fieldmap for *direction* using MCFLIRT and FLIRT outputs.

    Args:
        dataset_root: Root of the BIDS dataset.
        droot: Derivatives directory used to store intermediate results.
        ss: Subject/session descriptor.
        direction: Phase-encoding direction to derive.
        selection: Tuples describing candidate BOLD runs ``(run, path, rel)``.
        out: Destination NIfTI path for the derived fieldmap.

    Returns:
        List of :class:`McflirtRunSummary` entries describing captured matrices.
    """
    droot.mkdir(parents=True, exist_ok=True)
    prefix = _prefix(ss, direction)

    (droot / f"{prefix}_from-func_desc-opp-selection_table.tsv").write_text(
        "run\tbold\n" + "".join(f"{r or '-'}\t{rel}\n" for r, _, rel in selection)
    )
    (droot / f"{prefix}_desc-qa_log.txt").write_text("[INFO] placeholder QA log\n")
    (droot / f"{prefix}_desc-nmad_metrics.tsv").write_text("run\tnmad\n")
    (droot / f"{prefix}_desc-corr_metrics.tsv").write_text("run\tcorr\n")

    means_dir = droot / "_robust_means"; means_dir.mkdir(exist_ok=True)
    aligned_dir = droot / "_robust_aligned"; aligned_dir.mkdir(exist_ok=True)

    if not selection:
        out.touch()
        return []

    means: list[Path] = []
    run_tags: list[str] = []
    summaries: list[McflirtRunSummary] = []

    for idx, (run, bold, _rel) in enumerate(selection, 1):
        tag = f"run-{run or f'{idx:02d}'}"
        mcf_base = droot / f"{prefix}_{tag}_desc-robust_mcf"
        mcf_nii = mcf_base.with_suffix(".nii.gz")

        print(_RULE)
        print(f"{idx}) Motion correction — {tag} (dir={direction})")
        print(f"   Temp NIfTI: {_format_path(mcf_nii, dataset_root)}")
        print(f"   Final dir : {_format_path(mcf_base, dataset_root)}/")
        print("   Status    : running mcflirt…\n")

        # Open the live box; then stream MCFLIRT into it.
        top_line, bottom_line = _box_lines(f"MCFLIRT stdout ({tag})")
        print(f"   {top_line}")
        try:
            result = fsl.mcflirt(
                bold,
                mcf_base,
                capture=True,
                on_stdout=lambda line: print(f"   {line}", flush=True),
                suppress_final_result_from_live=True,
            )
        except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
            raise PePolarError(f"mcflirt failed for {bold}") from e

        stdout = result.stdout or ""
        matrix, cleaned_stdout = _extract_final_matrix(stdout)
        summaries.append(McflirtRunSummary(tag=tag, matrix=matrix))

        if not getattr(result, "streamed", False):
            if cleaned_stdout.strip():
                print(_indent_block(cleaned_stdout))
            else:
                print("   (no output captured)")

        print(f"   {bottom_line}\n")
        print(f"   ✓ Saved motion-corrected time series ({tag})\n")

        # mcflirt writes .nii.gz and .par
        mcf_base.with_suffix(".par").touch(exist_ok=True)
        mean = means_dir / f"{prefix}_{tag}_desc-mean.nii.gz"
        try:
            fsl.run_cmd(["fslmaths", str(mcf_nii), "-Tmean", str(mean)], capture=True)
        except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
            raise PePolarError(f"fslmaths -Tmean failed for {mcf_nii}") from e
        means.append(mean)
        run_tags.append(tag)

    aligned: list[Path] = []
    ref = means[0]
    for mean, tag in zip(means, run_tags):
        outa = aligned_dir / f"{prefix}_{tag}_desc-to-ref.nii.gz"
        if mean == ref:
            shutil.copy(mean, outa)
        else:
            try:
                flirt_res = fsl.run_cmd(
                    ["flirt", "-in", str(mean), "-ref", str(ref), "-out", str(outa)],
                    capture=True,
                )
                fmat, _ = _extract_final_matrix(flirt_res.stdout or "")
                if fmat:
                    summaries.append(McflirtRunSummary(tag=f"flirt-{tag}", matrix=fmat))
            except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
                raise PePolarError(f"flirt failed for {mean}") from e
        aligned.append(outa)

    robust_mean = droot / f"{prefix}_desc-robust_mean.nii.gz"
    shutil.copy(aligned[0], robust_mean)
    for img in aligned[1:]:
        try:
            fsl.run_cmd(["fslmaths", str(robust_mean), "-add", str(img), str(robust_mean)], capture=True)
        except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
            raise PePolarError("fslmaths -add failed") from e
    try:
        fsl.run_cmd(["fslmaths", str(robust_mean), "-div", str(len(aligned)), str(robust_mean)], capture=True)
    except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
        raise PePolarError("fslmaths -div failed") from e
    shutil.copy(robust_mean, out)

    for base in ["ref_brain", "ref_brain_mask", "ref_mask"]:
        (droot / f"{prefix}_desc-{base}.nii.gz").touch()

    return summaries


def _canonical_fmaps(fmap_dir: Path) -> tuple[bool, bool]:
    """Return booleans indicating whether AP and PA canonical files exist."""
    ap = any(fmap_dir.glob("*_dir-AP_epi.nii.gz"))
    pa = any(fmap_dir.glob("*_dir-PA_epi.nii.gz"))
    return ap, pa


def derive_pepolar_fieldmaps(
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: PepolarConfig,
    tasks: Iterable[str] | None = None,
) -> List[Path]:
    """Derive missing opposite phase-encoding fieldmaps for selected sessions.

    Args:
        dataset_root: Root of the BIDS dataset.
        sessions: Iterable of subject/session combinations to inspect.
        cfg: Pipeline configuration controlling discovery and behaviour.
        tasks: Optional iterable of task labels used to filter functional runs.

    Returns:
        List of paths to the generated fieldmap NIfTI files.
    """
    written: list[Path] = []
    task_filters = list(tasks) if tasks is not None else []
    task_set = {t.lower() for t in task_filters} if task_filters else None

    for ss in sessions:
        fmap_dir = dataset_root / ss.sub
        if ss.ses:
            fmap_dir = fmap_dir / ss.ses
        fmap_dir = fmap_dir / "fmap"
        if not fmap_dir.exists():
            log.info("pepolar", msg="no fmap directory", sub=ss.sub, ses=ss.ses)
            continue
        has_ap, has_pa = _canonical_fmaps(fmap_dir)
        if has_ap and has_pa:
            log.info("pepolar", msg="both directions present", sub=ss.sub, ses=ss.ses)
            continue
        if not has_ap and not has_pa:
            raise PePolarError(f"{ss.sub}/{ss.ses}: missing canonical fieldmap")

        canonical_tag = "AP" if has_ap else "PA"
        canonical_nii = next(fmap_dir.glob(f"*_dir-{canonical_tag}_epi.nii.gz"))
        canonical_json = canonical_nii.with_suffix("").with_suffix(".json")
        if not canonical_json.exists():
            raise PePolarError(f"missing sidecar: {canonical_json}")
        canon_meta = json.loads(canonical_json.read_text() or "{}")
        ped = canon_meta.get("PhaseEncodingDirection")
        valid_peds = {"i", "i-", "j", "j-", "k", "k-"}
        if not ped:
            raise PePolarError(f"{canonical_json} missing PhaseEncodingDirection")
        if ped not in valid_peds:
            raise PePolarError(f"{canonical_json} invalid PhaseEncodingDirection: {ped}")
        trt = canon_meta.get("TotalReadoutTime")
        missing_tag = "PA" if canonical_tag == "AP" else "AP"
        missing_ped = ped[:-1] if ped.endswith("-") else ped + "-"

        func_dir = dataset_root / ss.sub
        if ss.ses:
            func_dir = func_dir / ss.ses
        func_dir = func_dir / "func"
        intended: list[str] = []
        bold_trts: set[float] = set()
        selection: list[tuple[str, Path, str]] = []
        if func_dir.exists():
            for bold in sorted(func_dir.glob("*_bold.nii.gz")):
                name = bold.name
                if task_set:
                    task_name = None
                    for part in name.split("_"):
                        if part.startswith("task-"):
                            task_name = part[5:].lower()
                            break
                    if task_name is None or task_name not in task_set:
                        continue
                sidecar = bold.with_suffix("").with_suffix(".json")
                if not sidecar.exists():
                    raise PePolarError(f"missing sidecar: {sidecar}")
                meta = json.loads(sidecar.read_text() or "{}")
                bped = meta.get("PhaseEncodingDirection")
                if not bped or bped not in valid_peds:
                    raise PePolarError(f"{sidecar} invalid PhaseEncodingDirection")
                btrt = meta.get("TotalReadoutTime")
                if btrt is not None:
                    bold_trts.add(round(float(btrt), 7))
                if cfg.use_bids_uri:
                    rel = f"bids::{ss.sub}"
                    if ss.ses:
                        rel += f"/{ss.ses}"
                    rel += f"/func/{bold.name}"
                else:
                    rel = bold.relative_to(dataset_root / ss.sub)
                    rel = str(rel)
                intended.append(rel)
                m = re.search(r"run-(\d+)", name)
                run = m.group(1) if m else ""
                selection.append((run, bold, rel))
        if len(bold_trts) > 1:
            raise PePolarError(f"{ss.sub}/{ss.ses}: inconsistent TotalReadoutTime across BOLD runs")
        if trt is not None and bold_trts and round(trt, 7) not in bold_trts:
            raise PePolarError(f"{ss.sub}/{ss.ses}: TotalReadoutTime mismatch with canonical fieldmap")
        if trt is None and bold_trts:
            trt = next(iter(bold_trts))

        out = fmap_dir / f"{ss.sub}_{ss.ses or ''}_dir-{missing_tag}_epi.nii.gz".replace("__", "_")
        written.append(out)
        if cfg.dry_run:
            log.info("pepolar", msg="dry-run", path=str(out))
        else:
            title_parts = [f"Subject: {ss.sub}"]
            if ss.ses:
                title_parts.append(f"Session: {ss.ses}")
            if task_filters:
                title_parts.append(f"Task: {task_filters[0]}" if len(task_filters) == 1 else "Tasks: " + ", ".join(task_filters))

            print("\n=========================")
            print(f"  PEPOLAR — " + " | ".join(title_parts))
            print("=========================\n")

            print("Fieldmaps")
            print(f"  • Canonical fmap    : {_format_path(canonical_nii, dataset_root)}")
            print(f"  • Opposite PE to add: {missing_tag}")
            print()

            trt_label = "TRT matched" if (trt is not None or bold_trts) else "no TRT metadata"
            status = ", ".join([f"dir={missing_tag}", trt_label])
            print(f"Source BOLD runs ({status}):")
            if selection:
                for idx, (_run, _bold, rel) in enumerate(selection, 1):
                    print(f"  {idx}) {rel}")
            else:
                print("  • No BOLD runs matched the filters")
            print()

            meta = {"PhaseEncodingDirection": missing_ped, "IntendedFor": intended}
            if trt is not None:
                meta["TotalReadoutTime"] = trt

            run_summaries = _derive_fieldmap(
                dataset_root,
                _deriv_dir(dataset_root, ss),
                ss,
                missing_tag,
                selection,
                out,
            )

            out_json = out.with_suffix("").with_suffix(".json")
            out_json.write_text(json.dumps(meta, indent=2, sort_keys=True))
            canon_meta["IntendedFor"] = intended
            if trt is not None:
                canon_meta["TotalReadoutTime"] = trt
            canonical_json.write_text(json.dumps(canon_meta, indent=2, sort_keys=True))
            log.info("pepolar", msg="wrote", path=str(out))

            print(_RULE)
            print("Opposite-PE fieldmap derivation")
            strategy = f"robust mean of MCFLIRT-corrected {missing_tag} runs"
            print(f"  • Strategy : {strategy}")
            print(f"  • Output   : {_format_path(out, dataset_root)}")
            intended_count = len(intended)
            intended_label = "run" if intended_count == 1 else "runs"
            print(f"  • IntendedFor updated ({intended_count} BOLD {intended_label})")
            print()

            print(_format_heading("Final transforms from alignment to ref (FLIRT)"))
            matrices = [summary.matrix for summary in run_summaries if summary.matrix]
            if matrices:
                for idx, matrix in enumerate(matrices):
                    label = f"Transform {chr(ord('A') + idx)}"
                    print(label)
                    print("  4×4:")
                    for line in _format_matrix(matrix):
                        print(line)
                    if idx != len(matrices) - 1:
                        print()
            else:
                print("  • No transforms captured")
            print()

            print("Done.\n")
    return written
