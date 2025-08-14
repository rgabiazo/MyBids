"""Slug-cleaning helpers for merging DICOM series with identical descriptions.

All dataset-specific suffixes live in ``series.yaml → slug_cleanup.suffixes``.

Public surface
--------------
* :func:`build_cleanup_regex` – compile a *case-insensitive* pattern that
  matches **any** of the wildcard suffixes defined in YAML.
* :func:`clean_slug` – remove exactly **one** matching suffix from the input
  slug so that reconstructions such as ``_sbref`` or ``_fa`` do not create
  spurious sub-folders.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Iterable

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 1  Regex builder
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=None)
def build_cleanup_regex(suffixes: Iterable[str]) -> re.Pattern[str]:
    """Return a compiled pattern that matches *any* of the supplied suffixes.

    Args:
        suffixes: Iterable of wildcard patterns coming from
            ``slug_cleanup.suffixes``.  Each pattern may contain ``*`` which is
            expanded to the non-greedy regex token ``.*``.

    Returns:
        A **case-insensitive** :class:`re.Pattern` object.  The pattern anchors
        every alternative to ``$`` so only *terminal* matches are removed.

    Raises:
        RuntimeError: If *suffixes* is empty after stripping whitespace.
    """
    escaped: list[str] = []
    for raw in suffixes:
        txt = raw.strip().lower()
        if not txt:
            continue
        # Escape literal regex characters, then restore wildcard behaviour.
        txt = re.escape(txt).replace(r"\*", ".*")
        escaped.append(txt + r"$")  # anchor at end-of-string
    if not escaped:
        raise RuntimeError(
            "slug_cleanup.suffixes is empty – cannot build cleanup regex"
        )
    pat = re.compile("|".join(escaped), re.I)
    log.debug("[slug] cleanup regex = %s", pat.pattern)
    return pat


# ─────────────────────────────────────────────────────────────────────────────
# 2  Slug cleaner
# ─────────────────────────────────────────────────────────────────────────────
def clean_slug(text: str, regex: re.Pattern[str]) -> str:
    """Strip the *first* occurrence of *regex* from *text*.

    Args:
        text: Raw slug, typically derived from ``SeriesDescription`` or a folder
            name.
        regex: Pattern produced by :func:`build_cleanup_regex`.

    Returns:
        ``text`` without the first matching suffix.  If no match is found,
        ``text`` is returned unchanged.  The function never raises.

    Notes:
        Only **one** substitution is performed (``count=1``) so that inputs
        like ``rfMRI_SBRef_sbref`` lose the *first* ``_sbref`` and keep the
        remainder intact.
    """
    return regex.sub("", text, count=1)
