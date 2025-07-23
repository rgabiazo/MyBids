"""
Utility helpers for rendering *template* BIDS entity tables into
concrete values.

Key behaviours
--------------
1. **Prefix stripping** – Removes leading ``sub-`` / ``ses-`` so filenames
   never contain doubled prefixes (e.g. ``sub-sub-001``).
2. **Placeholder pruning** – Eliminates any ``{placeholder}`` whose runtime
   value is empty, mirroring logic used across all pipelines.
3. **Single source of truth** – Keeps entity rendering identical for
   anatomical, functional, diffusion, and any future pipelines.

Nothing in this file performs I/O.  All functions are deterministic and
side-effect-free, which makes them trivial to unit-test.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from bidscomatic.config.schema import BIDSEntities

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
# Matches placeholders such as "{sub}" or "{dir:02d}" inside YAML templates.
_PLACEHOLDER_RE = re.compile(r"\{(?P<key>\w+)(?::[^\}]+)?\}")

# ---------------------------------------------------------------------------
# Tiny helper – used only inside this module
# ---------------------------------------------------------------------------
def _strip_pref(value: str, pref: str) -> str:
    """Return *value* with *pref* removed when present."""
    return value[len(pref):] if isinstance(value, str) and value.startswith(pref) else value


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def render_entities(tmpl: BIDSEntities, **tokens: str) -> BIDSEntities:
    """Render a :class:`~bidscomatic.config.schema.BIDSEntities` template.

    Args:
        tmpl: Entity table originating from *series.yaml*.  Fields may still
            contain placeholders such as ``{sub}``, ``{ses}``, or ``{dir}``.
        **tokens: Concrete replacement values keyed by placeholder name.

    Returns:
        A new :class:`~bidscomatic.config.schema.BIDSEntities` instance with
        all resolvable placeholders substituted and any empty placeholders
        pruned.

    Notes:
        • Leading ``sub-`` / ``ses-`` prefixes are stripped from *tokens*
          to avoid doubled prefixes in filenames.
        • Unresolvable placeholders are preserved verbatim so downstream
          code can decide how to handle them.
    """
    # 1) Normalise tokens – drop common prefixes so values are bare IDs.
    clean: Dict[str, Any] = {
        k: _strip_pref(v, f"{k}-") if isinstance(v, str) else v
        for k, v in tokens.items()
    }

    rendered: Dict[str, Any] = {}
    for field, raw in tmpl.model_dump().items():
        # Non-string fields (int | None) are copied verbatim.
        if not isinstance(raw, str):
            rendered[field] = raw
            continue

        # (a) Remove placeholders whose value is missing or empty.
        def _remove_if_empty(match: re.Match[str]) -> str:
            """Prune ``{placeholder}`` when its corresponding value is blank."""
            key = match.group("key")
            return "" if clean.get(key) in {"", None} else match.group(0)

        safe_tmpl = _PLACEHOLDER_RE.sub(_remove_if_empty, raw)

        # (b) Try normal ``str.format`` substitution.
        try:
            rendered[field] = safe_tmpl.format(**clean)
        except (ValueError, KeyError):
            # Leave unresolved placeholders untouched for later handling.
            rendered[field] = safe_tmpl

    return BIDSEntities(**rendered)
