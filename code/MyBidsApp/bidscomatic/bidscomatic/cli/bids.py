"""Command-line entry point that orchestrates the high-level *bids* action.

* Resolves dataset roots and YAML configuration overrides.
* Expands subject/session paths before passing control to dedicated pipeline
  helpers (anatomical, functional, diffusion, field‑map).
* Provides a rich set of Click options while keeping business logic inside
  pipelines.
"""

from __future__ import annotations

import difflib
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple

import click
import structlog

from bidscomatic.config import load_config
from bidscomatic.utils.logging import _get_file_handler
from bidscomatic.utils.filters import (
    split_commas,  # reuse existing helper
    filter_subject_sessions,  # NEW session-level filter
    expand_session_roots,  # shared helper across CLI modules
)
from bidscomatic.pipelines.anatomical import (
    bidsify_anatomical,
    build_subtype_aliases,
)
from bidscomatic.pipelines.functional import bidsify_functional
from bidscomatic.pipelines.types import SubjectSession
from bidscomatic.cli.convert import _expand_subject_roots  # reuse helper
from bidscomatic.utils.display import (
    echo_banner,
    echo_subject_session,
    echo_success,
    echo_section,
)

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Regular expressions – loose ASCII alphanumerics after the prefix
# ---------------------------------------------------------------------------
_ID_RE = re.compile(r"^(sub|ses)-[A-Za-z0-9]+")


def _canon_id(txt: str) -> str:
    """Return the *sub-* or *ses-* prefix from *txt* if present.

    Args:
        txt: Raw string that may start with ``sub-`` or ``ses-``.

    Returns:
        The matching prefix if found, else the original string.
    """
    m = _ID_RE.match(txt)
    return m.group(0) if m else txt


def _detect_dataset_root(paths: Tuple[Path, ...]) -> Path | None:
    """Walk *paths* upwards to locate the nearest ``dataset_description.json``.

    Args:
        paths: Tuple of file system paths provided on the command line.

    Returns:
        The first ancestor that looks like a BIDS dataset root or *None* when
        no dataset is found.
    """
    for p in paths:
        cur = p.expanduser().resolve()
        for anc in (cur, *cur.parents):
            if (anc / "dataset_description.json").exists():
                return anc
    return None


# ---------------------------------------------------------------------------
# Helper callbacks – re‑implemented locally to keep import order unchanged
# ---------------------------------------------------------------------------
_TASK_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_VOL_RE = re.compile(r"^(\d+)$")


def _split_commas(_ctx, _param, values: tuple[str, ...]) -> tuple[str, ...]:
    """Click callback that flattens comma‑separated repeatable options.

    Mirrors :pyfunc:`bidscomatic.utils.filters.split_commas` so the module can
    remain self‑contained.
    """
    flat: list[str] = []
    for v in values:
        flat.extend(filter(None, (x.strip() for x in v.split(","))))
    return tuple(flat)


def _parse_func_specs(specs: tuple[str, ...]) -> tuple[list[str], bool, Dict[str, int]]:
    """Validate and split ``--func`` CLI parameters.

    Accepted patterns
    -----------------
    * ``task=<name>[@vols]`` – organise *task* runs and optionally restrict
      to a specific volume count.
    * ``task``             – organise *all* task runs.
    * ``rest[@vols]``      – organise resting‑state runs and optionally apply
      a volume filter.

    Args:
        specs: Raw ``--func`` option values collected by Click.

    Returns:
        Tuple consisting of
        ``(task_names, want_rest, volume_filters)``.

    Raises:
        click.ClickException: When a spec does not match the expected grammar.
    """
    tasks: list[str] = []
    vols: Dict[str, int] = {}
    want_rest = False
    if not specs:
        return [], False, {}

    for raw in specs:
        spec = raw.strip().lower()
        if spec.startswith("rest"):
            want_rest = True
            if "@" in spec:
                vols["rest"] = int(spec.split("@", 1)[1])
            continue
        if spec == "task":
            tasks.append("task")
            continue
        if not spec.startswith("task="):
            raise click.ClickException(
                f"Bad --func spec '{raw}'. Use 'task=<name>', 'task=<name>@<vols>', "
                "'task', or 'rest[@vols]'."
            )
        for chunk in spec[5:].split(","):
            name, _, v = chunk.partition("@")
            if not _TASK_RE.fullmatch(name):
                raise click.ClickException(f"Illegal task name '{name}'.")
            tasks.append(name)
            if v:
                vols[name] = int(v)
    return tasks, want_rest, vols


# ---------------------------------------------------------------------------
# Click command definition – “bids”
# ---------------------------------------------------------------------------
@click.command(
    name="bids",
    context_settings=dict(help_option_names=["-h", "--help"], max_content_width=120),
    help=(
        "Move NIfTIs from *sourcedata/nifti* into BIDS folders.\n\n"
        "Examples\n"
        "  bidscomatic-cli bids sourcedata/nifti --anat t1w,t2w\n"
        "  bidscomatic-cli bids sourcedata/nifti --func task=nback,rest\n"
        "  bidscomatic-cli bids sourcedata/nifti --dwi\n"
        "  bidscomatic-cli bids sourcedata/nifti --epi\n"
    ),
)
@click.argument(
    "paths",
    type=click.Path(path_type=Path),
    nargs=-1,
    required=True,
)
# ---------------- anatomical ----------------
@click.option(
    "--anat",
    "anat_tokens",
    multiple=True,
    callback=_split_commas,
    metavar="<subtype>",
)
# ---------------- functional ---------------
@click.option(
    "--func",
    "func_specs",
    multiple=True,
    callback=_split_commas,
    metavar="<spec>",
)
# ---------------- diffusion ----------------
@click.option(
    "--dwi/--no-dwi",
    default=False,
    show_default=True,
    help="Organise diffusion NIfTIs (and side-cars) into *dwi/*.",
)
# ---------------- field-maps ---------------
@click.option(
    "--epi/--no-epi",
    default=False,
    show_default=True,
    help="Populate missing opposite-phase *epi* field-maps.",
)
# --------------- subject  filters ---------------
@click.option(
    "--filter-sub",
    "filter_sub",
    multiple=True,
    callback=split_commas,
    metavar="<sub>",
    help="Only organise these subjects.",
)
# --------------- session filters ---------------
@click.option(
    "--filter-ses",
    "filter_ses",
    multiple=True,
    callback=split_commas,
    metavar="<ses>",
    help="Only organise these sessions.",
)
# ---------------- misc ----------------------
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    show_default=True,
)
@click.pass_obj
# noqa: D401 – Click callback name semantics.
def cli(  # type: ignore[override]
    ctx_obj,
    paths: Tuple[Path, ...],
    anat_tokens: Tuple[str, ...],
    func_specs: Tuple[str, ...],
    dwi: bool,
    epi: bool,
    overwrite: bool,
    filter_sub: Tuple[str, ...],
    filter_ses: Tuple[str, ...],
) -> None:
    """Run the ``bidscomatic-cli bids`` command.

    The function coordinates pipeline helpers based on CLI flags. Execution
    stops early when filters exclude all subjects/sessions.

    Args:
        ctx_obj: Click context object populated in :pyfunc:`bidscomatic.cli.main`.
        paths: Arbitrary mix of files or directories supplied on the command
            line.  The command resolves these into *subject* or *session*
            folders before any processing begins.
        anat_tokens: Requested anatomical subtypes from ``--anat``.
        func_specs: Functional specifications parsed from ``--func``.
        dwi: When *True* run the diffusion pipeline.
        epi: When *True* generate missing field‑maps.
        overwrite: Replace existing files when set.
        filter_sub: Subject filter values.
        filter_ses: Session filter values.
    """
    root: Path = ctx_obj["root"]

    # Auto‑detect dataset root from positional paths -------------------------
    auto_root = _detect_dataset_root(paths)
    if auto_root is not None:
        root = auto_root
        ctx_obj["root"] = root

    if not (root / "dataset_description.json").exists():
        raise click.ClickException(
            f"{root} has no dataset_description.json – run:\n\n"
            f"  bidscomatic-cli init {root} --name \"MyStudy\"\n"
        )

    cfg = ctx_obj["cfg"] or load_config(dataset_root=root)

    echo_banner("Organise BIDS")

    # Validate all provided paths -------------------------------------------
    good, bad = [], []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.exists():
            good.append(p)
        else:
            close = difflib.get_close_matches(p.name, [c.name for c in p.parent.glob("*")], n=1)
            bad.append(f"{p}" + (f" (did you mean {p.parent/close[0]}?)" if close else ""))
    if bad:
        raise click.ClickException("These PATHS do not exist:\n  " + "\n  ".join(bad))

    # Expand dataset‑level → subject → session -------------------------------
    paths = tuple(good)
    paths = _expand_subject_roots(paths)
    paths = expand_session_roots(tuple(paths))
    if not paths:
        click.echo("Nothing to do – no subject/session folders resolved.")
        return

    # Build SubjectSession objects ------------------------------------------
    sessions: list[SubjectSession] = []
    for p in paths:
        sub_raw = next((x for x in p.parts if x.startswith("sub-")), None)
        ses_raw = next((x for x in p.parts if x.startswith("ses-")), None)
        if not sub_raw:
            raise click.ClickException(f"{p} contains no 'sub-*' folder.")
        sessions.append(
            SubjectSession(
                root=root,
                sub=_canon_id(sub_raw),
                ses=_canon_id(ses_raw) if ses_raw else None,
            )
        )

    # Apply subject/session filter -----------------------------------------
    sessions = filter_subject_sessions(sessions, filter_sub, filter_ses)
    if not sessions:
        click.echo("Nothing left after --filter-sub / --filter-ses.")
        return

    for ss in sessions:
        echo_subject_session(ss.sub, ss.ses)

    # Anatomical pipeline ---------------------------------------------------
    if anat_tokens:
        if not ctx_obj["verbose"]:
            echo_section("Anatomical")
        ana_cfg = cfg.modalities["anatomical"]
        aliases = build_subtype_aliases(ana_cfg)
        wanted = [aliases[t.lower()] for t in anat_tokens if t.lower() in aliases]
        if wanted:
            bidsify_anatomical(
                dataset_root=root,
                sessions=sessions,
                cfg=cfg,
                subtypes=wanted,
                overwrite=overwrite,
            )
            echo_success("Anatomical organisation complete.")

    # Functional pipeline ---------------------------------------------------
    task_names, want_rest, vol_filter = _parse_func_specs(func_specs)
    if task_names or want_rest:
        if not ctx_obj["verbose"]:
            echo_section("Functional")
        bidsify_functional(
            dataset_root=root,
            sessions=sessions,
            cfg=cfg,
            overwrite=overwrite,
            tasks=task_names,
            include_rest=want_rest,
            vol_filter=vol_filter,
        )
        echo_success("Functional organisation complete.")

    # Diffusion pipeline ----------------------------------------------------
    if dwi:
        if not ctx_obj["verbose"]:
            echo_section("Diffusion")
        from bidscomatic.pipelines.diffusion import bidsify_diffusion

        bidsify_diffusion(
            dataset_root=root,
            sessions=sessions,
            cfg=cfg,
            overwrite=overwrite,
        )
        echo_success("Diffusion organisation complete.")

    # Field‑map pipeline ----------------------------------------------------
    if epi:
        if not ctx_obj["verbose"]:
            echo_section("EPI field-maps")
        from bidscomatic.pipelines.fieldmap import bidsify_fieldmaps

        bidsify_fieldmaps(
            dataset_root=root,
            sessions=sessions,
            cfg=cfg,
            overwrite=overwrite,
        )
        echo_success("EPI field-map organisation complete.")
