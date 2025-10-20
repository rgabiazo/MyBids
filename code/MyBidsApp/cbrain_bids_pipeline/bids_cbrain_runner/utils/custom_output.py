"""Utilities for rendering dynamic output directory names.

This module keeps the placeholder formatting logic separate from the CLI and
API plumbing so that it can be tested in isolation and reused by different
commands in the future.

The primary entry point is :class:`CustomOutputRenderer`, which consumes a
mapping of templates (e.g. ``{"output_dir_name": "{bids_dir}-{bold_task_type}"}``)
and produces concrete values by merging them with the tool parameters provided
on the command line.  It understands how to resolve CBRAIN userfile IDs into
their human-readable names, caches those lookups, and gracefully degrades to
literal text when a placeholder cannot be resolved.

Design goals
============
* **Stateless inputs** – The renderer accepts explicit context dictionaries so
  that callers can decide which parameters should be visible to templates.
* **Safe substitution** – ``string.Formatter`` is used under the hood but with
  a custom ``get_value`` implementation that falls back to the placeholder name
  rather than raising ``KeyError``.  This matches the desired behaviour of
  treating unknown fields as literal strings (``{foo}`` → ``foo``).
* **Logging & observability** – Rendering outcomes are logged with
  ``[INFO]``/``[WARN]``/``[ERROR]`` prefixes to make it easy to follow what the
  CLI resolved during a launch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from string import Formatter
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

from openapi_client.exceptions import ApiException

from ..api.client_openapi import CbrainClient

logger = logging.getLogger(__name__)

# Default keys whose values correspond to CBRAIN userfile identifiers.  The
# renderer resolves them into human-readable names so that templates can use the
# subject labels directly (e.g. ``{bids_dir}`` → ``sub-001``).
USERFILE_PARAM_KEYS: frozenset[str] = frozenset({"bids_dir", "fs_license_file"})


class _LiteralFallbackFormatter(Formatter):
    """``Formatter`` that returns the placeholder name when it is missing."""

    def get_value(self, key: Any, args: tuple[Any, ...], kwargs: Mapping[str, Any]):
        if isinstance(key, str):
            if key in kwargs and kwargs[key] is not None:
                return kwargs[key]
            # Fall back to the literal placeholder name (without braces).
            return key
        return super().get_value(key, args, kwargs)


@dataclass(slots=True)
class CustomOutputRenderer:
    """Render templated output directory names using tool parameters.

    Args:
        client: Authenticated :class:`CbrainClient` used to resolve userfile
            identifiers.
        userfile_keys: Optional iterable of parameter names that should be
            treated as userfile IDs.  Values for those keys are looked up via
            the CBRAIN API and replaced with their ``name`` fields inside the
            rendering context.
    """

    client: CbrainClient
    userfile_keys: Iterable[str] | None = None
    _name_cache: MutableMapping[int, str] = field(default_factory=dict, init=False)
    _userfile_keys: frozenset[str] = field(init=False)
    _formatter: _LiteralFallbackFormatter = field(init=False)

    def __post_init__(self) -> None:
        keys = set(USERFILE_PARAM_KEYS)
        if self.userfile_keys is not None:
            keys.update(self.userfile_keys)
        self._userfile_keys = frozenset(keys)
        self._formatter = _LiteralFallbackFormatter()

    def render(
        self,
        templates: Mapping[str, str],
        params: Mapping[str, Any],
        *,
        tool_name: str | None = None,
    ) -> Dict[str, str]:
        """Resolve ``templates`` against ``params`` and return substitutions."""

        if not templates:
            return {}

        context = self._build_context(params, tool_name=tool_name)
        resolved: Dict[str, str] = {}

        for key, template in templates.items():
            if not isinstance(template, str):
                logger.warning("[WARN] Custom output '%s' is not a string; skipping.", key)
                continue
            try:
                value = self._formatter.vformat(template, (), context)
            except Exception as exc:  # pragma: no cover - defensive guard
                logger.error(
                    "[ERROR] Could not render custom output '%s': %s",
                    key,
                    exc,
                )
                continue

            resolved[key] = value
            logger.info("[INFO] Custom output %s resolved to %s", key, value)

        return resolved

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_context(
        self,
        params: Mapping[str, Any],
        *,
        tool_name: str | None = None,
    ) -> Dict[str, Any]:
        """Return a formatting context augmented with userfile names."""

        context: Dict[str, Any] = dict(params)
        if tool_name:
            context.setdefault("tool_name", tool_name)
            context.setdefault("tool", tool_name)

        for key in self._userfile_keys:
            if key not in params:
                continue
            label = self._resolve_userfile_label(params[key])
            if label is None:
                continue
            context[f"{key}_id"] = params[key]
            context[f"{key}_name"] = label
            context[key] = label

        return context

    def _resolve_userfile_label(self, value: Any) -> Optional[str]:
        """Resolve ``value`` (if int-like) to a CBRAIN userfile name."""

        uid = self._coerce_userfile_id(value)
        if uid is None:
            return None

        if uid in self._name_cache:
            return self._name_cache[uid]

        try:
            record = self.client.get_userfile(uid)
        except ApiException as exc:
            logger.warning(
                "[WARN] Could not resolve userfile %s for custom outputs: %s",
                uid,
                exc,
            )
            return None

        if isinstance(record, dict):
            name = record.get("name")
        else:
            name = getattr(record, "name", None)

        if not name:
            logger.warning(
                "[WARN] Userfile %s has no name field; falling back to identifier.",
                uid,
            )
            name = str(uid)

        self._name_cache[uid] = name
        return name

    @staticmethod
    def _coerce_userfile_id(value: Any) -> Optional[int]:
        """Return an integer userfile ID when ``value`` looks like one."""

        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return int(stripped)
        return None

