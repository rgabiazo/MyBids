"""
CLI wrapper around :pymod:`bidscomatic.pipelines.convert`.

The command scans one or more DICOM directory trees, runs *dcm2niix* in
parallel, and writes the results to ``<BIDS_ROOT>/sourcedata/nifti`` by
default.

Key features
------------
* Subject/session discovery that tolerates dataset-level inputs.
* Optional merging of repeated series into a single folder driven by a
  slugified *SeriesDescription* (``--merge-by-name``).
* Fine-grained subject/session filtering (**--filter-sub / --filter-ses**).
* Preserves existing files unless **--overwrite** is passed further downstream
  (handled by the pipeline).

All public helpers added here remain import-safe for other CLI modules.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

import click
import structlog

from bidscomatic.utils.filters import (
    split_commas,
    filter_subject_session_paths,
    expand_session_roots,       # shared helper across CLI modules
)
from bidscomatic.utils.display import (
    echo_banner,
    echo_subject_session,
    echo_success,
)
from ..pipelines.convert import convert_dicom_tree

log = structlog.get_logger()
_SUB_RE = re.compile(r"sub-[A-Za-z0-9]+")


# ---------------------------------------------------------------------------
# Helper – expand dataset-level “dicom/” folders into concrete subject roots
# ---------------------------------------------------------------------------
def _expand_subject_roots(paths: Tuple[Path, ...]) -> List[Path]:
    """Return a list where dataset-level inputs become concrete *sub-* folders.

    Args:
        paths: Tuple of input paths supplied on the command line.  Each element
            may point at a dataset root, a subject folder, or any deeper level.

    Returns:
        List of paths where:
            * inputs that already contain ``sub-`` are kept unchanged;
            * dataset-level folders are replaced by their immediate ``sub-*``
              children (depth = 1);
            * non-directory paths are returned verbatim.
    """
    expanded: set[Path] = set()

    for p in paths:
        if _SUB_RE.search(str(p)):
            expanded.add(p)
            continue

        if not p.is_dir():
            expanded.add(p)
            continue

        children = [c for c in p.glob("sub-*") if c.is_dir()]
        expanded.update(children or [p])

    return sorted(expanded)


# ---------------------------------------------------------------------------
# Click command definition
# ---------------------------------------------------------------------------
@click.command(
    name="convert",
    help=(
        "Recursively convert DICOM → NIfTI with dcm2niix and place results under "
        "<BIDS_ROOT>/sourcedata/nifti.\n\n"
        "By default the destination mirrors the source hierarchy.  "
        "Use --merge-by-name to put all repeats (same SeriesDescription) "
        "into one folder."
    ),
)
@click.argument(
    "paths",
    type=click.Path(path_type=Path, exists=True),
    nargs=-1,
    required=True,
)
# ───────── destination / performance ────────────────────────────────────────
@click.option(
    "-o",
    "--output-root",
    type=click.Path(file_okay=False, path_type=Path),
    help="Override the default output root (default: <BIDS_ROOT>/sourcedata/nifti).",
)
@click.option(
    "-j",
    "--jobs",
    type=int,
    default=4,
    show_default=True,
    help="Maximum parallel dcm2niix jobs.",
)
# ───────── explicit entities ────────────────────────────────────────────────
@click.option("--sub", help="Explicit sub-XXX (else guessed).")
@click.option("--ses", help="Explicit ses-YYY (else guessed or per-series).")
# ───────── behaviour toggles ────────────────────────────────────────────────
@click.option(
    "--merge-by-name",
    is_flag=True,
    help=(
        "Merge all series with the same SeriesDescription slug "
        "into a single directory (alias of deprecated --sequential)."
    ),
)
@click.option(
    "--sequential",  # kept for backward-compat; hidden from --help
    is_flag=True,
    help="DEPRECATED alias for --merge-by-name.",
    hidden=True,
)
# ───────── subject / session filters ────────────────────────────────────────
@click.option(
    "--filter-sub",
    "filter_sub",
    multiple=True,
    callback=split_commas,
    metavar="<sub>",
    help="Only convert these subjects (IDs without the 'sub-' prefix).",
)
@click.option(
    "--filter-ses",
    "filter_ses",
    multiple=True,
    callback=split_commas,
    metavar="<ses>",
    help="Only convert these sessions (IDs without the 'ses-' prefix).",
)
# ---------------------------------------------------------------------------
@click.pass_obj
def cli(  # noqa: D401 – Click callback name semantics
    ctx_obj,
    paths: tuple[Path, ...],
    output_root: Path | None,
    jobs: int,
    sub: str | None,
    ses: str | None,
    merge_by_name: bool,
    sequential: bool,
    filter_sub: tuple[str, ...],
    filter_ses: tuple[str, ...],
) -> None:
    """Entry-point executed by *bidscomatic-cli convert*.

    All heavy lifting is delegated to :func:`bidscomatic.pipelines.convert.convert_dicom_tree`.

    Args:
        ctx_obj: Click context object populated in *bidscomatic.cli.main*.
        paths:   One or more filesystem paths supplied by the caller.
        output_root: Custom output directory.  Falls back to the BIDS dataset
            ``sourcedata/nifti`` tree when not provided.
        jobs:    Maximum parallel *dcm2niix* jobs.
        sub:     Explicit ``sub-XXX`` override.
        ses:     Explicit ``ses-YYY`` override.
        merge_by_name: When *True*, series having identical *SeriesDescription*
            slugs are written into the same destination folder.
        sequential: Deprecated alias kept for compatibility; internally mapped
            to ``merge_by_name``.
        filter_sub: Tuple of subject filters (without the ``sub-`` prefix).
        filter_ses: Tuple of session filters (without the ``ses-`` prefix).
    """
    merge_by_name = merge_by_name or sequential  # honour legacy flag

    root = ctx_obj["root"]
    out_base = output_root or (root / "sourcedata" / "nifti")

    echo_banner("Convert DICOM")

    # ------------------------------------------------------------------ Step 1
    # Expand dataset-level → subject → session folders
    targets = _expand_subject_roots(paths)
    targets = expand_session_roots(targets)

    # ------------------------------------------------------------------ Step 2
    # Apply sub/ses filters *before* scanning series
    targets = filter_subject_session_paths(targets, filter_sub, filter_ses)
    if not targets:
        raise click.ClickException("Nothing left after --filter-sub / --filter-ses.")

    grand_total_files = 0
    grand_total_series = 0

    # ------------------------------------------------------------------ Step 3
    # Convert every target folder independently
    for p in targets:
        log.info("Converting DICOM tree: %s", p)
        sub_id = next((x for x in p.parts if x.startswith("sub-")), str(p))
        ses_id = next((x for x in p.parts if x.startswith("ses-")), None)
        echo_subject_session(sub_id, ses_id)
        results = convert_dicom_tree(
            p,
            out_base,
            threads=jobs,
            sub=sub,
            ses=ses,
            merge_by_name=merge_by_name,
            logger=log,
        )
        total_files = sum(len(r.files) for r in results)
        grand_total_files += total_files
        grand_total_series += len(results)
        echo_success(
            f"{len(results)} series → {total_files} file(s) written under {out_base}"
        )

    # ------------------------------------------------------------------ Summary
    if len(targets) > 1:
        echo_success(
            f"{grand_total_series} series across {len(targets)} subject folders → {grand_total_files} file(s) total"
        )
