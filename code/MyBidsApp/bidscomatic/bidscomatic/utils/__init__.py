"""
Public façade for the *utils* package.

Anything imported here becomes part of the *stable* public API.
Internal helpers live in their own modules and are **not** re-exported.
"""

from __future__ import annotations

# ─── participants helpers ────────────────────────────────────────────────
from .participants import (
    collect_subject_ids,
    load_metadata,
    parse_assignments,
    merge_participants,
    tidy_columns,
    write_participants,
)

# ─── generic filters / path helpers ──────────────────────────────────────
from .filters import (
    split_commas,
    filter_subject_session_paths,
    filter_subject_sessions,
    expand_session_roots,
)

# ─── archive / cleanup ───────────────────────────────────────────────────
from .cleanup import delete_archives, delete_dcm_roots

# ─── slug & naming helpers ───────────────────────────────────────────────
from .naming import slugify
from .slug   import build_cleanup_regex, clean_slug

# ─── questionnaire utils ─────────────────────────────────────────────────
from .questionnaires import load_questionnaire_csv, make_tsv_frames

# ─── events utils (NEW) ──────────────────────────────────────────────────
from .events import make_events_frames, infer_dir_tag           # ★ NEW ★
from .validator import find_bids_root_upwards, run_bids_validator
from .display import echo_banner, echo_subject_session, echo_success, echo_section
from .motion import (
    fd_power_from_par,
    fd_from_confounds,
    stream_dvars,
    stream_tsnr,
    load_mask,
    RunMetrics,
)
from .paths import dataset_root_or_raise, qc_root_for_file, qc_run_dir

# ------------------------------------------------------------------------
__all__: list[str] = [
    # participants
    "collect_subject_ids",
    "load_metadata",
    "parse_assignments",
    "merge_participants",
    "tidy_columns",
    "write_participants",
    # filters
    "split_commas",
    "filter_subject_session_paths",
    "filter_subject_sessions",
    "expand_session_roots",
    # cleanup
    "delete_archives",
    "delete_dcm_roots",
    # slug helpers
    "slugify",
    "build_cleanup_regex",
    "clean_slug",
    # questionnaires
    "load_questionnaire_csv",
    "make_tsv_frames",
    # events
    "make_events_frames",                    # ★ NEW ★
    "infer_dir_tag",                         # ★ NEW ★
    "find_bids_root_upwards",
    "run_bids_validator",
    "echo_banner",
    "echo_subject_session",
    "echo_success",
    "echo_section",
    "dataset_root_or_raise",
    "qc_root_for_file",
    "qc_run_dir",
    "fd_power_from_par",
    "fd_from_confounds",
    "stream_dvars",
    "stream_tsnr",
    "load_mask",
    "RunMetrics",
]
