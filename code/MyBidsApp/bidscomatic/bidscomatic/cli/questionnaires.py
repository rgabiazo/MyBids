"""
Generate BIDS-ready TSVs for questionnaires and place them into *phenotype/*.

The command is invoked as ``bidscomatic-cli questionnaires``.  It expects a
wide-format spreadsheet that contains one column per questionnaire item.  Each
questionnaire is identified by a common prefix (e.g. ``PHQ9_*``) which becomes
the filename stem in the output TSV.

Notes
------------
* Accepts CSV, TSV, XLS, or XLSX as input.
* Supports single-session and multi-session layouts (``--session-mode``).
* Column dropping (``--omit``) and renaming (``--rename-cols``) are available.
* Respects ``--overwrite`` to avoid accidental data loss.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import click
import structlog

from bidscomatic.utils.filters import split_commas
from bidscomatic.utils.questionnaires import (
    load_questionnaire_csv,
    make_tsv_frames,
)
from bidscomatic.utils.participants import collect_subject_ids, _canon_pid
from bidscomatic.utils.phenotype_json import build_metadata, write_json
from bidscomatic.utils.logging import _get_file_handler  # optional plain-text mirror
from bidscomatic.utils.display import echo_banner, echo_subject_session, echo_success

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Click command definition
# ---------------------------------------------------------------------------
@click.command(
    name="questionnaires",
    help="Create TSV files in phenotype/ from a multi-session questionnaire CSV.",
    context_settings=dict(
        help_option_names=["-h", "--help"], show_default=True, max_content_width=120
    ),
)
@click.argument(
    "csv_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
)
# ---------------- basic output ----------------
@click.option(
    "-o",
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    help="Destination directory (default: <BIDS_ROOT>/phenotype).",
)
# --------------- selection --------------------
@click.option(
    "--questionnaires",
    "q_names",
    multiple=True,
    callback=split_commas,
    metavar="<name>",
    help="One or more questionnaire prefixes (comma-separated or repeatable). "
    "Use 'all' to include every questionnaire in the input file.",
)
@click.option(
    "--session-mode",
    type=click.Choice(["single", "multi"]),
    default="multi",
)
@click.option(
    "--subjects",
    multiple=True,
    callback=split_commas,
    metavar="<sub>",
    help="Only include these subjects (IDs with or without the 'sub-' prefix).",
)
@click.option(
    "--all-subjects",
    is_flag=True,
    help="Process every row in the CSV regardless of available subject folders.",
)
# --------------- column filters ---------------
@click.option(
    "--omit",
    callback=split_commas,
    multiple=True,
    metavar="<token>",
    help="Drop columns whose name contains any of these tokens.",
)
@click.option(
    "--rename-cols",
    "rename_cols",
    callback=split_commas,
    multiple=True,
    metavar="<old>=<new>",
    help="Rename columns after extraction.",
)
# --------------- misc -------------------------
@click.option("--id-col", default="participant_id", show_default=True)
@click.option("--overwrite", is_flag=True, help="Overwrite existing TSVs.")
@click.pass_obj
def cli(  # noqa: D401 – Click callback naming convention
    ctx_obj,
    csv_path: Path,
    output_dir: Path | None,
    q_names: Tuple[str, ...],
    session_mode: str,
    subjects: Tuple[str, ...],
    all_subjects: bool,
    omit: Tuple[str, ...],
    rename_cols: Tuple[str, ...],
    id_col: str,
    overwrite: bool,
) -> None:
    """Entry-point executed by ``bidscomatic-cli questionnaires``.

    Args:
        ctx_obj: Click context populated in *bidscomatic.cli.main*.
        csv_path: Path to the input spreadsheet.
        output_dir: Optional destination directory; defaults to
            ``<BIDS_ROOT>/phenotype``.
        q_names: Questionnaire prefixes to extract or the literal ``all``.
        session_mode: ``single`` (one TSV) or ``multi`` (one TSV per session).
        subjects: Optional subject filter (with/without ``sub-`` prefix).
        all_subjects: Include every row from the CSV regardless of detected
            subject folders when *True*.
        omit: Case-insensitive substring filter for columns to drop.
        rename_cols: Tuple of ``old=new`` rename specifications.
        id_col: Column that holds participant IDs.
        overwrite: Overwrite existing TSVs when *True*.
    """
    root: Path = ctx_obj["root"]
    echo_banner("questionnaires")

    subj_list: list[str] | None = list(subjects) if subjects else None
    if not all_subjects:
        dataset_subs = collect_subject_ids(root)
        if not dataset_subs:
            click.echo("No sub-* folders found – nothing to do.")
            return
        if subj_list:
            wanted = {_canon_pid(s) for s in subj_list}
            dataset_subs = [s for s in dataset_subs if s in wanted]
        subj_list = dataset_subs

    for sid in subj_list or []:
        sid_disp = sid if sid.startswith("sub-") else f"sub-{sid}"
        echo_subject_session(sid_disp, None)

    out_dir = output_dir or (root / "phenotype")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------- load input ---------------------------------
    df = load_questionnaire_csv(
        csv_path,
        id_col=id_col,
        subjects=tuple(subj_list) if subj_list else None,
        omit=omit,
    )

    if not all_subjects and subj_list:
        df = df.reindex([s for s in subj_list if s in df.index])

    # ------------------------ parse rename specifications ---------------------
    rename_map = {}
    for spec in rename_cols:
        if "=" not in spec:
            raise click.ClickException(f"--rename-cols bad spec '{spec}'")
        old, new = [s.strip() for s in spec.split("=", 1)]
        rename_map[old] = new

    # -------------------------- build output frames ---------------------------
    frames = make_tsv_frames(
        df,
        prefixes=list(q_names),
        session_mode=session_mode,
        rename_cols=rename_map,
    )
    if not frames:
        raise click.ClickException("No matching questionnaire columns found.")

    # ------------------------------- write TSVs -------------------------------
    force_overwrite = overwrite or not all_subjects
    for fname, frame in frames.items():
        dst = out_dir / fname
        if dst.exists() and not force_overwrite:
            log.info("[questionnaires] %s exists – skipped", dst.relative_to(root))
            continue
        frame.to_csv(dst, sep="\t", index=False, na_rep="n/a")
        log.info("[questionnaires] wrote %s", dst.relative_to(root))

        # plain-text mirror log (when configured globally)
        fh = _get_file_handler(None)  # returns None when not requested
        if fh:
            fh.emit(
                log.makeRecord(
                    "INFO", 20, __file__, 0, f"[questionnaires] wrote {dst}", None, None
                )
            )

        # -------------------- minimal side-car JSON --------------------------
        meta = build_metadata(dst, custom=None)
        write_json(dst, metadata=meta, overwrite=True, root=root)

    echo_success(f"{len(frames)} TSV file(s) written in {out_dir}")
