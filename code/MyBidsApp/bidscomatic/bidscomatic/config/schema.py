"""
Pydantic models that mirror the YAML configuration consumed by *bidscomatic*.

The classes in this module define a strongly-typed representation of the
configuration file so that the rest of the codebase can work with validated
objects instead of ad-hoc dictionaries.

Notes:
* Entities follow the BIDS specification with ``dir`` appearing before ``run``
  in generated filenames (``…_dir-AP_run-01…``).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# 1.  Leaf models – immutable value objects                                   #
# --------------------------------------------------------------------------- #


class BIDSEntities(BaseModel):
    """Key/value pairs representing BIDS filename entities.

    Unknown placeholders inside the YAML are rejected early to avoid silent
    misspellings that would surface only much later during filename rendering.
    """

    # --------------------------------------------------------------------- #
    # Pre-processing – accept both wrapped and flat YAML styles             #
    # --------------------------------------------------------------------- #

    @model_validator(mode="before")
    @classmethod
    def _merge_nested_entities(cls, values: dict):
        """Lift keys from an ``entities:`` sub-mapping to the parent dict."""
        if isinstance(values, dict) and "entities" in values:
            nested = values.pop("entities") or {}
            if isinstance(nested, dict):
                # Nested entries override any duplicates at the parent level.
                values.update(nested)
        return values

    # --------------------------------------------------------------------- #
    # Entity fields                                                         #
    # --------------------------------------------------------------------- #
    sub: str = Field("{sub}", description="BIDS subject identifier")
    ses: str = Field("{ses}", description="BIDS session identifier")

    run: Optional[str] = None
    dir: Optional[str] = None
    task: Optional[str] = None
    acq: Optional[str] = None
    label: Optional[str] = None  # Enables {label} templating in YAML

    suffix: str = Field(..., description="BIDS filename suffix")

    # --------------------------- validators ------------------------------ #
    _RE_TEMPLATE = re.compile(r"{(.*?)}")
    _ALLOWED_TOKENS = {"sub", "ses", "run", "dir", "task", "label"}

    @model_validator(mode="after")
    def _tokens_are_known(self):
        """Ensure every ``{placeholder}`` in the YAML is a known token."""
        tokens = {
            m.group(1).split(":", 1)[0]  # Ignore optional format spec
            for v in self.__dict__.values()
            if isinstance(v, str)
            for m in self._RE_TEMPLATE.finditer(v)
        }
        unknown = tokens - self._ALLOWED_TOKENS
        if unknown:
            raise ValueError("Unknown placeholder(s): " + ", ".join(sorted(unknown)))
        return self

    # --------------------------- convenience ----------------------------- #
    # dir precedes run per the BIDS specification: '..._dir-AP_run-01_...'
    _ORDER = ["sub", "ses", "task", "acq", "dir", "run", "label"]

    def as_pairs(self) -> List[tuple[str, str]]:
        """Return entity pairs in canonical BIDS order.

        Returns:
            List of ``(key, value)`` tuples suitable for
            :pyclass:`bidscomatic.models.BIDSPath`.
        """
        data = self.model_dump(exclude_none=True)
        data.pop("suffix", None)  # *suffix* is not an entity

        pairs: List[tuple[str, str]] = []

        # First emit the canonical ordering…
        for key in self._ORDER:
            if key in data:
                pairs.append((key, data.pop(key)))

        # …then any remaining entities alphabetically (rare edge cases).
        pairs.extend(sorted(data.items()))
        return pairs


class Sequence(BaseModel):
    """Scanner-sequence definition.

    Attributes:
        sequence_id: Prefix expected in raw filenames (e.g. ``T1w``).
        bids:        Rendered :class:`BIDSEntities` describing the target file.
        parameters:  Optional list used to expand the mapping (e.g. ``["AP",
                      "PA"]`` for phase-encoding direction).
        scan_types:  Optional nested mapping providing per-scan overrides.
        label:       Optional static label substituted for ``{label}`` tokens.
    """

    sequence_id: str = Field(..., description="Prefix found in raw filenames")
    bids: BIDSEntities

    parameters: Optional[List[str]] = None
    scan_types: Optional[Dict[str, Dict]] = None
    label: Optional[str] = None


# --------------------------------------------------------------------------- #
# 2.  File-handling rules (ignore / rename)                                   #
# --------------------------------------------------------------------------- #


class IgnoreSection(BaseModel):
    """Patterns defining which archives and files to ignore.

    Attributes:
        archives: Glob patterns of archives that should be skipped.
        files: Glob patterns of files that should be skipped.
    """

    archives: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)


class FileRules(BaseModel):
    """Top-level *files.yaml* structure.

    Attributes:
        ignore: Rules specifying archives and files that should be skipped.
        rename: Mapping of source filenames to the desired target names.
    """

    ignore: IgnoreSection = Field(default_factory=IgnoreSection)
    rename: Dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# 3.  Top-level model – complete validated config                             #
# --------------------------------------------------------------------------- #


class ConfigSchema(BaseModel):
    """Root configuration object consumed by the rest of *bidscomatic*.

    Attributes:
        version: Version string of the configuration schema.
        modalities: Mapping of imaging modalities to defined sequences.
        files: Optional rules for ignoring and renaming files.
    """

    version: str
    modalities: Dict[str, Dict[str, Sequence]]
    files: FileRules = Field(default_factory=FileRules)
