"""
Helpers for ``--reassign-session`` flag in the *bids* workflow.

The public functions parse arbitrary reassignment strings and normalise
individual subject/session tokens into canonical BIDS labels.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Public type alias used elsewhere in the code-base
ReassignSpec = Tuple[str, str, str, str]


# -----------------------------------------------------------------------------#
# Parsing                                                                      #
# -----------------------------------------------------------------------------#
def parse_reassign_specs(specs: List[str]) -> List[ReassignSpec]:
    """Expand *specs* list into individual reassignment tuples.

    Input grammar (informal)
    ------------------------
        OLD_SUB:OLD_SES=NEW_SUB[:NEW_SES][,NEW_SUB[:NEW_SES]…]
        […]
    Multiple comma-separated right-hand targets are allowed per expression.

    Args:
        specs: Raw strings passed on the CLI.

    Returns:
        List of four-element tuples
        ``(old_sub, old_ses, new_sub, new_ses)``.  All elements remain
        whatever text appeared in the spec; no normalisation is applied here.
    """
    out: List[ReassignSpec] = []
    for spec in specs:
        if "=" not in spec:
            continue
        lhs, rhs = spec.split("=", 1)
        if ":" not in lhs:
            continue
        old_sub, old_ses = lhs.split(":", 1)

        # Handle multiple targets: NEW1,NEW2:SES, …
        for tgt in rhs.split(","):
            if ":" in tgt:
                new_sub, new_ses = tgt.split(":", 1)
            else:
                new_sub, new_ses = tgt, old_ses
            out.append(
                (old_sub.strip(), old_ses.strip(), new_sub.strip(), new_ses.strip())
            )
    return out


# -----------------------------------------------------------------------------#
# Normalisation                                                                 #
# -----------------------------------------------------------------------------#
def normalize_label(
    sub: str,
    ses: str,
    session_map: Dict[str, str],
) -> Tuple[str, str]:
    """Return canonical BIDS subject and session labels.

    Args:
        sub: Input subject token.  Accepts plain numbers (``"71"``) or full
            ``"sub-071"`` strings.
        ses: Input session token.  Accepts numbers, ``ses-##`` strings, or
            descriptive trailing tags that exist in *session_map*.
        session_map: Mapping of trailing tag → two-digit session number.

    Returns:
        Tuple ``("sub-###", "ses-##")``.

    Raises:
        ValueError: *sub* or *ses* token does not conform to expected patterns.
    """
    # ---- Subject label -------------------------------------------------
    try:
        sub_lbl = f"sub-{int(sub):03d}"
    except ValueError:
        # Might already be “sub-###”
        m = re.fullmatch(r"sub-(\d{1,})", sub)
        if m:
            sub_lbl = f"sub-{int(m.group(1)):03d}"
        else:
            raise ValueError(f"Invalid subject '{sub}'")

    # ---- Session label -------------------------------------------------
    s = ses.lower()
    if s.isdigit():
        ses_lbl = f"ses-{int(s):02d}"
    elif s.startswith("ses-"):
        ses_lbl = s
    elif s in session_map:
        ses_lbl = f"ses-{session_map[s]}"
    else:
        raise ValueError(f"Unknown session tag '{ses}'")

    return sub_lbl, ses_lbl
