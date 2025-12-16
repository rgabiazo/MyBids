"""High level pipeline to derive opposite phase-encoding fieldmaps.

This pipeline derives missing opposite `*_dir-<X>_epi` fieldmaps (PEPOLAR-style)
from functional BOLD runs that were acquired with the opposite
PhaseEncodingDirection.

Design goals:
- Mirror the behaviour of the historical Bash script while remaining testable.
- Keep implementation lightweight (file IO + simple FSL command wrappers).
- Support arbitrary BIDS `dir-` label pairs via :class:`~bidscomatic.config.pepolar.PepolarConfig`.
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

_DIR_ENTITY_RE = re.compile(r"(?:^|_)dir-(?P<dir>[A-Za-z0-9]+)(?:_|$)")
_VALID_PEDS = {"i", "i-", "j", "j-", "k", "k-"}


@dataclass
class McflirtRunSummary:
    """Container capturing MCFLIRT/FLIRT artefacts for summary reporting."""

    tag: str
    matrix: list[list[float]]


def _format_path(path: Path, base: Path | None = None) -> str:
    """Return *path* in POSIX form, relative to *base* when possible."""
    as_posix = path.as_posix()
    if base is not None:
        try:
            rel = path.relative_to(base)
        except ValueError:
            return as_posix
        return f"…/{rel.as_posix()}"
    return as_posix


def _box_lines(title: str) -> tuple[str, str]:
    """Return the top and bottom border strings for a box with *title*."""
    filler = max(_BOX_WIDTH - len(title), 0)
    top = f"┌─ {title} " + ("─" * filler)
    bottom = "└" + ("─" * (len(top) - 1))
    return top, bottom


def _indent_block(text: str, prefix: str = "   ") -> str:
    """Indent *text* with *prefix* after normalising newline characters."""
    if not text:
        return ""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").rstrip()
    return textwrap.indent(cleaned, prefix)


def _extract_final_matrix(stdout: str) -> tuple[list[list[float]], str]:
    """Return the final 4×4 matrix parsed from MCFLIRT/FLIRT stdout.

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

    # Remove all "Final result" blocks (defensive: some tools may emit multiple).
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
    """Return the derivatives directory for MCFLIRT outputs."""
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


def _nifti_stem(path: Path) -> str:
    """Return the filename without .nii[.gz] suffix."""
    name = path.name
    if name.endswith(".nii.gz"):
        return name[:-7]
    if name.endswith(".nii"):
        return name[:-4]
    return path.stem


def _json_sidecar(path: Path) -> Path:
    """Return the JSON sidecar path for a NIfTI image."""
    if path.name.endswith(".nii.gz"):
        return path.with_suffix("").with_suffix(".json")
    return path.with_suffix(".json")


def _collapse_underscores(value: str) -> str:
    """Collapse consecutive underscores in *value*."""
    return re.sub(r"__+", "_", value).strip("_")


def _extract_dir_label(stem: str) -> str | None:
    """Extract the BIDS ``dir-`` entity value from a filename stem."""
    match = _DIR_ENTITY_RE.search(stem)
    if not match:
        return None
    return match.group("dir")


def _drop_dir_entity(stem: str) -> str:
    """Return *stem* with the ``_dir-<X>`` entity removed."""
    return _collapse_underscores(re.sub(r"(?:^|_)dir-[A-Za-z0-9]+(?=_|$)", "", stem))


def _discover_fmap_epi_groups(fmap_dir: Path) -> dict[str, dict[str, Path]]:
    """Group EPI fieldmap NIfTIs by their stem with ``dir-`` removed.

    Returns:
        Mapping ``group_key -> {dir_label -> nifti_path}``.
    """
    groups: dict[str, dict[str, Path]] = {}
    patterns = ("*_epi.nii.gz", "*_epi.nii")
    for pattern in patterns:
        for nii in fmap_dir.glob(pattern):
            if not nii.is_file():
                continue
            stem = _nifti_stem(nii)
            dir_label = _extract_dir_label(stem)
            if not dir_label:
                continue
            key = _drop_dir_entity(stem)
            bucket = groups.setdefault(key, {})
            if dir_label in bucket:
                raise PePolarError(
                    f"duplicate fieldmap epi for {key} dir-{dir_label}: {bucket[dir_label].name} vs {nii.name}"
                )
            bucket[dir_label] = nii
    return dict(sorted(groups.items(), key=lambda kv: kv[0]))


def _coerce_float(value: object, *, field: str, path: Path) -> float:
    """Coerce *value* to float with a helpful error message."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise PePolarError(f"{path} invalid {field}: {value!r}") from exc


def _flip_ped(ped: str) -> str:
    """Return the opposite-sign BIDS PhaseEncodingDirection."""
    return ped[:-1] if ped.endswith("-") else ped + "-"


def _format_intended_for(
    dataset_root: Path,
    ss: SubjectSession,
    bold: Path,
    *,
    use_bids_uri: bool,
) -> str:
    """Format an IntendedFor entry for *bold*."""
    if use_bids_uri:
        rel = f"bids::{ss.sub}"
        if ss.ses:
            rel += f"/{ss.ses}"
        rel += f"/func/{bold.name}"
        return rel

    # For BIDS IntendedFor, use paths relative to the subject folder when possible.
    try:
        rel_path = bold.relative_to(dataset_root / ss.sub)
    except ValueError:
        rel_path = bold.relative_to(dataset_root)
    return rel_path.as_posix()


def _derive_missing_name(canonical_name: str, canonical_dir: str, missing_dir: str) -> str:
    """Build the missing fieldmap filename by swapping the dir- entity.

    This preserves any other entities present in the canonical filename
    (e.g., ``acq-``, ``run-``, etc.).
    """
    token_a = f"_dir-{canonical_dir}_"
    token_b = f"_dir-{missing_dir}_"
    if token_a in canonical_name:
        return canonical_name.replace(token_a, token_b, 1)

    token_a = f"_dir-{canonical_dir}_epi"
    token_b = f"_dir-{missing_dir}_epi"
    if token_a in canonical_name:
        return canonical_name.replace(token_a, token_b, 1)

    # Fall back to a simple string replacement.
    return canonical_name.replace(f"dir-{canonical_dir}", f"dir-{missing_dir}", 1)


def _derive_fieldmap(
    dataset_root: Path,
    droot: Path,
    ss: SubjectSession,
    direction: str,
    selection: list[tuple[str, Path, str]],
    out: Path,
) -> list[McflirtRunSummary]:
    """Derive a fieldmap for *direction* using MCFLIRT and FLIRT outputs."""
    droot.mkdir(parents=True, exist_ok=True)
    prefix = _prefix(ss, direction)

    (droot / f"{prefix}_from-func_desc-opp-selection_table.tsv").write_text(
        "run\tbold\n" + "".join(f"{r or '-'}\t{rel}\n" for r, _, rel in selection)
    )
    (droot / f"{prefix}_desc-qa_log.txt").write_text("[INFO] placeholder QA log\n")
    (droot / f"{prefix}_desc-nmad_metrics.tsv").write_text("run\tnmad\n")
    (droot / f"{prefix}_desc-corr_metrics.tsv").write_text("run\tcorr\n")

    means_dir = droot / "_robust_means"
    means_dir.mkdir(exist_ok=True)
    aligned_dir = droot / "_robust_aligned"
    aligned_dir.mkdir(exist_ok=True)

    if not selection:
        # Upstream selection logic should prevent this; keep guard for clarity.
        raise PePolarError(f"{ss.sub}/{ss.ses}: no BOLD runs selected for dir-{direction}")

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

        stdout = getattr(result, "stdout", "") or ""
        matrix, cleaned_stdout = _extract_final_matrix(stdout)
        summaries.append(McflirtRunSummary(tag=tag, matrix=matrix))

        # If mcflirt didn't stream live output, print whatever we captured.
        if not getattr(result, "streamed", False):
            if cleaned_stdout.strip():
                print(_indent_block(cleaned_stdout))
            else:
                print("   (no output captured)")

        print(f"   {bottom_line}\n")
        print(f"   ✓ Saved motion-corrected time series ({tag})\n")

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
                fmat, _ = _extract_final_matrix(getattr(flirt_res, "stdout", "") or "")
                if fmat:
                    summaries.append(McflirtRunSummary(tag=f"flirt-{tag}", matrix=fmat))
            except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
                raise PePolarError(f"flirt failed for {mean}") from e
        aligned.append(outa)

    robust_mean = droot / f"{prefix}_desc-robust_mean.nii.gz"
    shutil.copy(aligned[0], robust_mean)
    for img in aligned[1:]:
        try:
            fsl.run_cmd(
                ["fslmaths", str(robust_mean), "-add", str(img), str(robust_mean)],
                capture=True,
            )
        except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
            raise PePolarError("fslmaths -add failed") from e

    try:
        fsl.run_cmd(
            ["fslmaths", str(robust_mean), "-div", str(len(aligned)), str(robust_mean)],
            capture=True,
        )
    except subprocess.CalledProcessError as e:  # pragma: no cover - defensive
        raise PePolarError("fslmaths -div failed") from e

    shutil.copy(robust_mean, out)

    # Create placeholder artefacts used by downstream QA steps.
    for base in ["ref_brain", "ref_brain_mask", "ref_mask"]:
        (droot / f"{prefix}_desc-{base}.nii.gz").touch()

    return summaries


def derive_pepolar_fieldmaps(
    dataset_root: Path,
    sessions: Iterable[SubjectSession],
    cfg: PepolarConfig,
    tasks: Iterable[str] | None = None,
) -> List[Path]:
    """Derive missing opposite phase-encoding fieldmaps for selected sessions.

    For each subject/session, look for ``*_dir-<X>_epi`` fieldmaps under
    ``fmap/``. When only one side of a configured `dir-` pair exists (e.g. PA
    without AP), derive the missing file by building a robust mean image from
    BOLD runs whose PhaseEncodingDirection matches the missing fieldmap.

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

        groups = _discover_fmap_epi_groups(fmap_dir)
        if not groups:
            raise PePolarError(f"{ss.sub}/{ss.ses}: no *_dir-*_epi fieldmaps found under fmap/")

        for key, dir_map in groups.items():
            present_dirs = sorted(dir_map.keys())
            if len(present_dirs) > 2:
                raise PePolarError(
                    f"{ss.sub}/{ss.ses}: fieldmap group {key} has more than two dir values: {present_dirs}"
                )

            if len(present_dirs) == 2:
                d0, d1 = present_dirs
                if cfg.dir_pairs.get(d0) == d1 and cfg.dir_pairs.get(d1) == d0:
                    log.info(
                        "pepolar",
                        msg="fieldmap pair already present",
                        sub=ss.sub,
                        ses=ss.ses,
                        group=key,
                        dirs=present_dirs,
                    )
                    continue
                raise PePolarError(
                    f"{ss.sub}/{ss.ses}: ambiguous fieldmap group {key} with dirs={present_dirs}"
                )

            # At this point len(present_dirs) == 1 and we need to derive the opposite.
            canonical_dir = present_dirs[0]
            missing_dir = cfg.dir_pairs.get(canonical_dir)
            if not missing_dir:
                raise PePolarError(
                    f"{ss.sub}/{ss.ses}: cannot infer opposite for dir-{canonical_dir}. "
                    f"Provide --dir-pair {canonical_dir}=<OPP>."
                )

            canonical_nii = dir_map[canonical_dir]
            canonical_json = _json_sidecar(canonical_nii)
            if not canonical_json.exists():
                raise PePolarError(f"missing sidecar: {canonical_json}")

            try:
                canon_meta = json.loads(canonical_json.read_text() or "{}")
            except json.JSONDecodeError as exc:
                raise PePolarError(f"invalid JSON: {canonical_json}") from exc

            ped = canon_meta.get("PhaseEncodingDirection")
            if not ped:
                raise PePolarError(f"{canonical_json} missing PhaseEncodingDirection")
            if ped not in _VALID_PEDS:
                raise PePolarError(f"{canonical_json} invalid PhaseEncodingDirection: {ped}")

            missing_ped = _flip_ped(ped)
            canon_axis = ped[:-1] if ped.endswith("-") else ped

            trt = canon_meta.get("TotalReadoutTime")
            trt_val = None if trt is None else _coerce_float(trt, field="TotalReadoutTime", path=canonical_json)

            func_dir = dataset_root / ss.sub
            if ss.ses:
                func_dir = func_dir / ss.ses
            func_dir = func_dir / "func"

            if not func_dir.exists():
                raise PePolarError(
                    f"{ss.sub}/{ss.ses}: missing func/ directory required to derive dir-{missing_dir}"
                )

            intended: list[str] = []
            bold_trts: set[float] = set()
            selection: list[tuple[str, Path, str]] = []

            # Discover candidate BOLD runs.
            bold_files: list[Path] = []
            for pattern in ("*_bold.nii.gz", "*_bold.nii"):
                bold_files.extend(func_dir.glob(pattern))
            bold_files = sorted({p for p in bold_files if p.is_file()})

            for bold in bold_files:
                name = bold.name

                if task_set:
                    m = re.search(r"_task-([A-Za-z0-9]+)", name)
                    task_name = m.group(1).lower() if m else None
                    if task_name is None or task_name not in task_set:
                        continue

                sidecar = _json_sidecar(bold)
                if not sidecar.exists():
                    raise PePolarError(f"missing sidecar: {sidecar}")

                try:
                    meta = json.loads(sidecar.read_text() or "{}")
                except json.JSONDecodeError as exc:
                    raise PePolarError(f"invalid JSON: {sidecar}") from exc

                bped = meta.get("PhaseEncodingDirection")
                if not bped or bped not in _VALID_PEDS:
                    raise PePolarError(f"{sidecar} invalid PhaseEncodingDirection")

                baxis = bped[:-1] if bped.endswith("-") else bped
                if baxis != canon_axis:
                    log.info(
                        "pepolar",
                        msg="skipping bold with mismatched phase-encode axis",
                        bold=str(bold),
                        bold_ped=bped,
                        fmap_ped=ped,
                    )
                    continue

                btrt = meta.get("TotalReadoutTime")
                if btrt is not None:
                    bold_trts.add(round(_coerce_float(btrt, field="TotalReadoutTime", path=sidecar), 7))

                rel = _format_intended_for(dataset_root, ss, bold, use_bids_uri=bool(cfg.use_bids_uri))
                intended.append(rel)

                run_m = re.search(r"run-(\d+)", name)
                run = run_m.group(1) if run_m else ""
                if bped == missing_ped:
                    selection.append((run, bold, rel))

            if not intended:
                raise PePolarError(
                    f"{ss.sub}/{ss.ses}: no eligible BOLD runs found to populate IntendedFor "
                    f"(tasks={task_filters or 'ALL'})"
                )
            if not selection:
                raise PePolarError(
                    f"{ss.sub}/{ss.ses}: no BOLD runs found with PhaseEncodingDirection={missing_ped} "
                    f"to derive missing dir-{missing_dir} EPI"
                )

            if len(bold_trts) > 1:
                raise PePolarError(f"{ss.sub}/{ss.ses}: inconsistent TotalReadoutTime across BOLD runs")
            if trt_val is not None and bold_trts and round(trt_val, 7) not in bold_trts:
                raise PePolarError(f"{ss.sub}/{ss.ses}: TotalReadoutTime mismatch with canonical fieldmap")
            if trt_val is None and bold_trts:
                trt_val = next(iter(bold_trts))

            out = fmap_dir / _derive_missing_name(canonical_nii.name, canonical_dir, missing_dir)
            written.append(out)

            if cfg.dry_run:
                log.info("pepolar", msg="dry-run", path=str(out))
                continue

            title_parts = [f"Subject: {ss.sub}"]
            if ss.ses:
                title_parts.append(f"Session: {ss.ses}")
            if task_filters:
                title_parts.append(
                    f"Task: {task_filters[0]}"
                    if len(task_filters) == 1
                    else "Tasks: " + ", ".join(task_filters)
                )

            print("\n=========================")
            print("  PEPOLAR — " + " | ".join(title_parts))
            print("=========================\n")

            print("Fieldmaps")
            print(f"  • Canonical fmap    : {_format_path(canonical_nii, dataset_root)}")
            print(f"  • Opposite PE to add: {missing_dir}")
            print()

            trt_label = "TRT matched" if (trt_val is not None or bold_trts) else "no TRT metadata"
            status = ", ".join([f"dir={missing_dir}", trt_label])
            print(f"Source BOLD runs ({status}):")
            for idx, (_run, _bold, rel) in enumerate(selection, 1):
                print(f"  {idx}) {rel}")
            print()

            meta_out: dict[str, object] = {"PhaseEncodingDirection": missing_ped, "IntendedFor": intended}
            if trt_val is not None:
                meta_out["TotalReadoutTime"] = trt_val

            run_summaries = _derive_fieldmap(
                dataset_root,
                _deriv_dir(dataset_root, ss),
                ss,
                missing_dir,
                selection,
                out,
            )

            out_json = _json_sidecar(out)
            out_json.write_text(json.dumps(meta_out, indent=2, sort_keys=True))

            # Update canonical fmap JSON to include the same IntendedFor and TRT.
            canon_meta["IntendedFor"] = intended
            if trt_val is not None:
                canon_meta["TotalReadoutTime"] = trt_val
            canonical_json.write_text(json.dumps(canon_meta, indent=2, sort_keys=True))

            log.info("pepolar", msg="wrote", path=str(out))

            print(_RULE)
            print("Opposite-PE fieldmap derivation")
            strategy = f"robust mean of MCFLIRT-corrected {missing_dir} runs"
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
