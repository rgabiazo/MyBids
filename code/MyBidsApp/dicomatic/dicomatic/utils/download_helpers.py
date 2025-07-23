"""
Helpers that interface with **cfmm2tar** for archive retrieval.

This module is intentionally thin on business logic.  All path / naming
decisions are delegated to :pymod:`dicomatic.utils.planning`.
It does:

* Provides legacy shims so historical import paths keep working.
* Wraps the actual Docker command invocation for one study UID.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import warnings
from pathlib import Path
from typing import Any, Dict, List, Tuple

import click

from dicomatic.models import DownloadPlan
from dicomatic.utils.naming import build_bids_basename, sanitize_for_filename  # noqa: F401
from dicomatic.utils.planning import build_plans

log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------#
# Legacy wrappers (kept for API stability)                                     #
# -----------------------------------------------------------------------------#
def plan_downloads(
    grouped: Dict[str, Dict[str, List[Dict[str, str]]]],
    bids_root: str,
    use_session_dirs: bool = True,
) -> List[DownloadPlan]:
    """Convert a grouped study mapping into :class:`DownloadPlan` objects.

    Deprecated:
        Call :func:`dicomatic.utils.planning.build_plans` directly.  This
        wrapper exists only for callers outside the repository.

    Args:
        grouped: ``{sub:{ses:[studies]}}`` structure.
        bids_root: Absolute path to the BIDS root.
        use_session_dirs: ``False`` flattens single-session layouts.

    Returns:
        List of download plans ready for execution.
    """
    warnings.warn(
        "plan_downloads() is deprecated; call utils.planning.build_plans() instead",
        DeprecationWarning,
        stacklevel=2,
    )

    studies = [
        st
        for sessions in grouped.values()
        for slist in sessions.values()
        for st in slist
    ]
    return build_plans(
        studies=studies,
        bids_root=Path(bids_root),
        flatten=not use_session_dirs,
    )


def generate_dry_run_paths(
    grouped: Dict[str, Dict[str, List[Dict[str, str]]]],
    bids_root: str,
    use_session_dirs: bool = True,
) -> List[Path]:
    """Return absolute paths that *would* be created for the given grouping."""
    return [
        p.path
        for p in plan_downloads(grouped, bids_root, use_session_dirs=use_session_dirs)
    ]


# -----------------------------------------------------------------------------#
# Interactive-prompt convenience                                               #
# -----------------------------------------------------------------------------#
def extract_download_overrides(
    study: Dict[str, str],
    all_studies: List[Dict[str, str]],
    cfg: Any,
) -> Tuple[str, str, bool]:
    """Infer sensible CLI defaults for downloading a single study.

    Args:
        study:        The chosen study dict (contains `patient_name`, etc.).
        all_studies:  Full list from which *study* was selected.
        cfg:          Active configuration namespace; only used for heuristics.

    Returns:
        Tuple of ``(subject_label, session_number_without_prefix, no_session_dirs)``.
    """
    # Subject folder is simply a filesystem-safe PatientName
    sub_label = sanitize_for_filename(study.get("patient_name", ""))

    # Heuristic: if the same patient appears on >1 dates, assume multiple sessions
    same_patient = [
        s for s in all_studies if s.get("patient_name") == study.get("patient_name")
    ]
    multi_session = len({s.get("study_date") for s in same_patient}) > 1
    ses_label = "01"  # default numeric label
    no_session_dirs = not multi_session

    return sub_label, ses_label, no_session_dirs


# -----------------------------------------------------------------------------#
# Core download implementation                                                 #
# -----------------------------------------------------------------------------#
def download_study(
    study: Dict[str, str],
    cfg: Any,
    target_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Run a cfmm2tar Docker container to pull one study archive.

    Args:
        study:      Raw study dict containing at least ``study_uid``.
        cfg:        Loaded configuration namespace (YAML + CLI overrides).
        target_dir: Directory that will receive the ``.tar`` archive.
        dry_run:    Skip execution; print the command only.
        verbose:    When ``True`` stream cfmm2tar stdout/stderr to console.

    Returns:
        ``True`` on success (or when skipping because the file exists);
        ``False`` when the subprocess fails.
    """
    uid = study.get("study_uid")
    if not uid:
        raise ValueError("study dict missing 'study_uid'")

    target_dir.mkdir(parents=True, exist_ok=True)

    # Short-circuit: non-attached tar already present
    if any(
        p.suffix == ".tar" and not p.name.endswith(".attached.tar")
        for p in target_dir.iterdir()
    ):
        click.echo(f"[SKIP] {target_dir.name} (already downloaded)")
        return True

    # ------------------------------------------------------------------#
    # Credential file handling                                           #
    # ------------------------------------------------------------------#
    creds_file = Path(
        getattr(cfg.dicom, "credentials_file", "")
        or os.path.expanduser("~/.uwo_credentials")
    )
    temp_creds: str | None = None  # path to temp file (deleted afterwards)

    if not creds_file.exists():
        # Fall back to inline username/password → write temp creds file
        if not (cfg.dicom.username and cfg.dicom.password):
            raise RuntimeError("No credentials file and no username/password")
        tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
        tf.write(f"{cfg.dicom.username}\n{cfg.dicom.password}\n")
        tf.flush()
        tf.close()
        creds_file = Path(tf.name)
        temp_creds = tf.name

    # ------------------------------------------------------------------#
    # Build Docker command line                                          #
    # ------------------------------------------------------------------#
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{creds_file}:/tmp/creds:ro",
        "-v",
        f"{target_dir}:/data",
        "-w",
        "/data",
        cfg.dicom.container,
        "-c",
        "/tmp/creds",
        "-u",
        uid,
        "/data",
    ]

    click.echo(f"> Running: {' '.join(cmd)}")
    click.echo(f"> output directory → {target_dir}")

    # ------------------------------------------------------------------#
    # Execute (or dry-run)                                               #
    # ------------------------------------------------------------------#
    if dry_run:
        if temp_creds:
            os.remove(temp_creds)
        return True

    try:
        subprocess.run(cmd, check=True, capture_output=not verbose)
        click.echo(f"[ Download Complete ] → {target_dir}")
        ok = True
    except subprocess.CalledProcessError as exc:
        log.error("Download of %s failed: %s", uid, exc)
        click.echo(f"[ERROR] Download failed for {uid}")
        ok = False
    finally:
        # Clean up temporary credentials file on disk
        if temp_creds:
            try:
                os.remove(temp_creds)
            except OSError:
                pass

    return ok
