"""CLI-parsing helpers for dicomatic.

This module gathers small utilities used by Click option callbacks so
that command modules stay focused on I/O orchestration.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

__all__: list[str] = ["parse_session_flags"]


def parse_session_flags(raw: List[str]) -> List[Tuple[Optional[str], str]]:
    """Convert ``--filter-session`` values to ``(subject|None, session)`` tuples.

    The helper accepts both syntaxes:

    * **One-token form** (new): ``"01"``, ``"ses-01"``, ``"072:01"``
    * **Two-token form** (legacy): values arrive in consecutive order,
      e.g. ``["072", "01"]``

    Args:
        raw: Sequence of option values exactly as Click captured them.

    Returns:
        List of normalised ``(subject, session)`` tuples suitable for
        :func:`dicomatic.bids.filters.filter_grouped_studies`.
    """
    out: List[Tuple[Optional[str], str]] = []
    buf: List[str] = []

    for tok in raw:
        tok = tok.strip()
        buf.append(tok)

        # When two tokens accumulate, treat them as subject + session.
        if len(buf) == 2:
            subj_tok, ses_tok = buf
            out.append(_split_token(f"{subj_tok}:{ses_tok}"))
            buf.clear()
            continue

        # Attempt immediate one-token parse.
        if _is_single_token(tok):
            out.append(_split_token(tok))
            buf.clear()
            continue

    # Ignore a stray unpaired token to keep behaviour lenient.
    return out


# --------------------------------------------------------------------- #
# Internal helpers                                                      #
# --------------------------------------------------------------------- #
def _is_single_token(tok: str) -> bool:
    """Return ``True`` when *tok* contains ``":"`` or looks like a session."""
    return ":" in tok or tok.startswith("ses-") or (tok.isdigit() and len(tok) <= 2)


def _split_token(tok: str) -> Tuple[Optional[str], str]:
    """Break *tok* into ``(subject|None, session)`` with canonical labels."""
    if ":" in tok:  # explicit subject prefix
        subj, ses = tok.split(":", 1)
        subj_key = _norm_sub(subj)
    else:
        subj_key, ses = None, tok

    return subj_key, _norm_ses(ses)


def _norm_sub(val: str) -> Optional[str]:
    """Return a canonical ``sub-XXX`` label or ``None`` for empty strings."""
    if not val:
        return None
    m = re.fullmatch(r"(?:sub-)?0*(\d+)", val)
    return f"sub-{int(m.group(1)):03d}" if m else val


def _norm_ses(val: str) -> str:
    """Return a canonical ``ses-XX`` label."""
    return f"ses-{int(val):02d}" if val.isdigit() else val
