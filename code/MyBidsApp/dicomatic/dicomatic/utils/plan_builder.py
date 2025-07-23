"""
Backward-compatibility shim for legacy imports.

The historical public function ``build_download_plans`` now redirects to
:pyfunc:`dicomatic.utils.planning.build_plans`.  Only minimal glue code
lives here; new logic must be placed in *planning.py*.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from click import Context

# Re-export ensures ``from … import build_download_plans`` keeps working
# Import the real implementation under an internal name so the wrapper can
# call it without recursing into itself.  ``build_download_plans`` remains the
# public symbol for backward compatibility.
from dicomatic.utils.planning import build_plans as _build_plans

__all__ = ["build_download_plans"]


# -----------------------------------------------------------------------------#
# Legacy wrapper                                                                #
# -----------------------------------------------------------------------------#
def build_download_plans(  # type: ignore[override]
    ctx: Context,
    desc: Optional[str] = None,
    uids: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    subject_override: Optional[str] = None,
    session_override: Optional[str] = None,
    no_session_dirs: bool = False,
):
    """Return :class:`DownloadPlan` objects using the original call signature.

    Args:
        ctx: Click context containing the loaded configuration namespace.
        desc: Optional *StudyDescription* filter.
        uids: Optional explicit ``StudyInstanceUID`` list.
        output_dir: Destination root for archives.  When ``None``,
            the BIDS root discovered from config or cwd is used.
        subject_override: Fixed *sub-XXX* label for all plans.
        session_override: Fixed session label (numeric or ``ses-YY``).
        no_session_dirs: When ``True`` omit the *ses-YY* subfolder for
            single-session layouts.

    Returns:
        List of :class:`dicomatic.models.DownloadPlan` objects.
    """
    # Local import avoids circular dependencies with Click command modules
    from dicomatic.commands._shared import fetch_studies, fetch_studies_by_uids

    cfg = ctx.obj
    uids = list(uids) if uids else []

    # ------------------------------------------------------------------#
    # Resolve BIDS root                                                 #
    # ------------------------------------------------------------------#
    if output_dir:
        bids_root = Path(output_dir).resolve()
    else:
        from dicomatic.utils.project_root import find_bids_root

        bids_root = Path(cfg.bids.root or find_bids_root()).resolve()

    # ------------------------------------------------------------------#
    # Acquire study dictionaries                                        #
    # ------------------------------------------------------------------#
    if uids and not desc:
        studies = fetch_studies_by_uids(ctx, uids)
    else:
        studies = fetch_studies(ctx, desc) if desc else []
        if uids:
            # Filter down to requested UIDs when *desc* is also supplied
            studies = [s for s in studies if s.get("study_uid") in uids]

    # ------------------------------------------------------------------#
    # Build overrides map when both pieces are present                  #
    # ------------------------------------------------------------------#
    overrides = None
    if subject_override and session_override:
        overrides = {"sub": subject_override, "ses": session_override}

    # ------------------------------------------------------------------#
    # Delegate to modern single-source planner                          #
    # ------------------------------------------------------------------#
    return _build_plans(
        studies=studies,
        bids_root=bids_root,
        overrides=overrides,
        flatten=no_session_dirs,
    )
