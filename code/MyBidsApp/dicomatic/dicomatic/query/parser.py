"""Parse ``findscu`` text output into study dictionaries.

A mapping supplied at runtime (``tag_map``) associates DICOM tags and VRs
with destination keys.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


def parse_studies_with_demographics(
    output: str,
    tag_map: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    """Convert ``findscu`` output into structured study records.

    The dcm4che tool emits lines such as::

        (0010,0010) PN [DOE^JOHN]
        ...
        status=ff00H   # interim
        ...
        status=0H      # final

    The parser builds one dictionary per ``status`` boundary.

    Args:
        output: Raw stdout captured from the ``findscu`` subprocess.
        tag_map: Mapping of DICOM attribute keyword to a dictionary with the
            ``group_elem``, ``vr``, and ``field`` entries.

    Returns:
        list[dict]: Study dictionaries suitable for downstream helpers.
    """
    # ------------------------------------------------------------------ #
    # 1. Build reverse lookup: (group_elem, vr) → destination key        #
    # ------------------------------------------------------------------ #
    reverse_map: Dict[Tuple[str, str], str] = {
        (info["group_elem"], info["vr"]): info["field"] for info in tag_map.values()
    }

    # Prepare an empty record template covering every expected field
    template: Dict[str, str] = {info["field"]: None for info in tag_map.values()}
    current: Dict[str, str] = template.copy()
    studies: List[Dict[str, str]] = []

    # ------------------------------------------------------------------ #
    # 2. Iterate over each output line                                   #
    # ------------------------------------------------------------------ #
    for line in output.splitlines():
        # Match attribute lines: "(0010,0010) PN [DOE^JOHN]"
        m = re.match(r"^\(([\da-fA-F]{4},[\da-fA-F]{4})\)\s+(\S+)\s+\[(.*)\]", line)
        if m:
            group_elem = f"({m.group(1)})"
            vr = m.group(2)
            value = m.group(3).strip()  # Raw DICOM value, whitespace trimmed
            field = reverse_map.get((group_elem, vr))
            if field:
                current[field] = value

        # A status line indicates the end of one C-FIND record
        if "status=ff00H" in line or "status=0H" in line:
            # Only append records that contain a StudyInstanceUID
            if current.get("study_uid"):
                studies.append(dict(current))
            current = template.copy()  # Reset for next record

    # ------------------------------------------------------------------ #
    # 3. Handle any trailing record without explicit status line         #
    # ------------------------------------------------------------------ #
    if current.get("study_uid"):
        studies.append(dict(current))

    return studies
