"""
Metadata manifest writer.

Maintains a single *metadata.json* file that records provenance for each
downloaded archive.  Entries are keyed by ``study_instance_uid`` to avoid
duplication across repeated pulls or resumed downloads.
"""

from __future__ import annotations

import json
import os
import glob  # retained for future use; currently unused but part of original API
from datetime import datetime
from pathlib import Path
from typing import List

from dicomatic.models import DownloadPlan

# -----------------------------------------------------------------------------#
# Internal helpers                                                             #
# -----------------------------------------------------------------------------#
def _read_existing(path: Path) -> List[dict]:
    """Return parsed JSON content or an empty list when the file is absent."""
    if not path.is_file():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001 – tolerate malformed files silently
        return []


# -----------------------------------------------------------------------------#
# Public API                                                                    #
# -----------------------------------------------------------------------------#
def write_metadata(
    plans: List[DownloadPlan],
    metadata_path: str,
    cfmm2tar_version: str,
) -> None:
    """Insert or merge *plans* into *metadata_path*.

    Args:
        plans: Sequence of :class:`DownloadPlan` objects to record.
        metadata_path: Destination JSON path (created or updated).
        cfmm2tar_version: Version string stored alongside each entry for
            provenance tracking.

    Behaviour:
        * The file is created when missing.
        * Entries are unique per ``study_instance_uid``; newer information
          replaces older records.
        * Output is sorted by ``participant_id``, ``session_id``, and
          ``study_date`` for stable diffs in version control.
    """
    meta_path = Path(metadata_path)
    existing_entries = _read_existing(meta_path)
    by_uid = {
        e["study_instance_uid"]: e
        for e in existing_entries
        if "study_instance_uid" in e
    }

    meta_dir = meta_path.parent

    for plan in plans:
        st = plan.study
        uid = st["study_uid"]

        # Determine actual on-disk filename; fall back to first *.tar
        expected = plan.path
        if not expected.exists():
            tar_dir = plan.path.parent
            candidates = [
                p for p in tar_dir.glob("*.tar") if not p.name.endswith(".attached.tar")
            ]
            if candidates:
                expected = candidates[0]

        entry = {
            "participant_id": plan.sub_label,
            "session_id": plan.ses_label,
            "archive_filename": expected.name,
            "archive_relative_path": os.path.relpath(expected, meta_dir),
            "study_description": st.get("study_description", ""),
            "study_date": st.get("study_date", ""),
            "study_instance_uid": uid,
            "patient_age": st.get("patient_age", ""),
            "patient_sex": st.get("patient_sex", ""),
            "retrieval_date": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "cfmm2tar_version": cfmm2tar_version,
        }
        by_uid[uid] = entry  # newer entry overwrites any existing one

    # Sorted list ensures deterministic output order
    merged = sorted(
        by_uid.values(),
        key=lambda e: (e["participant_id"], e["session_id"], e["study_date"]),
    )

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
