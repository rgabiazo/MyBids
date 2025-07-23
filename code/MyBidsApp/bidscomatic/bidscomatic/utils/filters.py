"""
Subject/session selection utilities and path-expansion helpers.

Public surface
--------------
* ``split_commas`` – Click callback to flatten repeated or comma-separated
  options.
* ``filter_subject_session_paths`` – keep only *Path* objects that match the
  requested *sub-* / *ses-* filters.
* ``filter_subject_sessions`` – identical purpose for
  :class:`~bidscomatic.pipelines.types.SubjectSession` instances.
* ``expand_session_roots`` – turn a *subject* directory into its concrete
  ``ses-*`` sub-directories.

All helpers operate purely on strings and ``pathlib.Path`` objects, so they
stay side-effect-free and easy to unit-test.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Sequence, Set

# --------------------------------------------------------------------------- #
# Regular-expressions – deliberately liberal (ASCII letters + digits only)    #
# --------------------------------------------------------------------------- #
_SUB_RE = re.compile(r"sub-([A-Za-z0-9]+)", re.I)
_SES_RE = re.compile(r"ses-([A-Za-z0-9]+)", re.I)


# --------------------------------------------------------------------------- #
# 0.  Tiny helper – flatten repeat/CSV Click options                          #
# --------------------------------------------------------------------------- #
def split_commas(_ctx, _param, values: tuple[str, ...]) -> tuple[str, ...]:
    """Return a flat tuple from a *repeatable* / comma-separated Click option.

    Args:
        _ctx: Click context (ignored, required by Click callback signature).
        _param: Click parameter (ignored).
        values: Tuple emitted by Click for the option.

    Returns:
        Tuple with every comma-separated token stripped and deduplicated.
    """
    flat: list[str] = []
    for v in values:
        flat.extend(filter(None, (x.strip() for x in v.split(","))))
    return tuple(flat)


# --------------------------------------------------------------------------- #
# 1.  Internals – subject/session extractors & canonicalisation               #
# --------------------------------------------------------------------------- #
def _sub_of(p: Path) -> str | None:
    """Extract the **subject ID** from *p* or return *None* if absent."""
    for part in p.parts:
        if (m := _SUB_RE.fullmatch(part)):
            return m.group(1)
    return None


def _ses_of(p: Path) -> str | None:
    """Extract the **session ID** from *p* or return *None* if absent."""
    for part in p.parts:
        if (m := _SES_RE.fullmatch(part)):
            return m.group(1)
    return None


def _canon(tokens: Iterable[str]) -> Set[str]:
    """Return a canonicalised, lower-case set of IDs.

    Leading ``sub-`` / ``ses-`` prefixes are stripped so that command-line
    filters may be written with or without them.

    Args:
        tokens: Raw ID strings supplied by the caller.

    Returns:
        Set with normalised tokens suitable for direct equality checks.
    """
    out: set[str] = set()
    for t in tokens:
        if not t:
            continue
        t = t.lower()
        t = re.sub(r"^(sub|ses)-", "", t)  # remove prefix if present
        out.add(t)
    return out


# --------------------------------------------------------------------------- #
# 2.  Public filters                                                          #
# --------------------------------------------------------------------------- #
def filter_subject_session_paths(
    paths: Iterable[Path],
    subs: Sequence[str] | None = None,
    sess: Sequence[str] | None = None,
) -> List[Path]:
    """Return only those *paths* that match the requested filters.

    Args:
        paths: Arbitrary iterable of filesystem paths.
        subs: Subject IDs to keep (with or without ``sub-`` prefix).
        sess: Session IDs to keep (with or without ``ses-`` prefix).

    Returns:
        Sorted list of paths that meet both criteria.
    """
    want_sub = _canon(subs or [])
    want_ses = _canon(sess or [])

    keep: list[Path] = []
    for p in paths:
        s = _sub_of(p)
        se = _ses_of(p)

        # Subject filter ---------------------------------------------------
        if want_sub and (s is None or s.lower() not in want_sub):
            continue
        # Session filter ---------------------------------------------------
        if want_ses and (se is None or se.lower() not in want_ses):
            continue
        keep.append(p)

    return sorted(keep)


def filter_subject_sessions(
    ss_iter,
    subs: Sequence[str] | None = None,
    sess: Sequence[str] | None = None,
):
    """Filter :class:`SubjectSession` objects by subject and session IDs.

    Args:
        ss_iter: Iterable of objects exposing ``.sub`` and ``.ses`` fields.
        subs: Subject IDs to keep.
        sess: Session IDs to keep.

    Returns:
        List with elements that satisfy the supplied filters.
    """
    want_sub = _canon(subs or [])
    want_ses = _canon(sess or [])

    def _ok(ss) -> bool:  # duck-typing keeps dependency surface minimal.
        """Return ``True`` when *ss* matches the requested subject/session."""
        if want_sub and ss.sub.removeprefix("sub-").lower() not in want_sub:
            return False
        if want_ses:
            if ss.ses is None:
                return False
            if ss.ses.removeprefix("ses-").lower() not in want_ses:
                return False
        return True

    return [ss for ss in ss_iter if _ok(ss)]


# --------------------------------------------------------------------------- #
# 3.  Helper – expand subject roots to concrete session folders               #
# --------------------------------------------------------------------------- #
def expand_session_roots(paths: Iterable[Path]) -> List[Path]:
    """Expand *subject-level* directories into concrete ``ses-*`` folders.

    Behaviour:
        * Path already contains a session component → unchanged.
        * Directory with child ``ses-*`` sub-dirs → children returned.
        * Anything else → original path preserved.

    Args:
        paths: Iterable of paths (files or directories).

    Returns:
        Deduplicated, sorted list of paths suitable for further processing.
    """
    out: set[Path] = set()
    for p in paths:
        # Already concrete -------------------------------------------------
        if any(part.startswith("ses-") for part in p.parts):
            out.add(p)
            continue

        # Cannot descend into non-directories ------------------------------
        if not p.is_dir():
            out.add(p)
            continue

        # Look one level for ses-* children --------------------------------
        kids = [c for c in p.glob("ses-*") if c.is_dir()]
        out.update(kids or [p])

    return sorted(out)
