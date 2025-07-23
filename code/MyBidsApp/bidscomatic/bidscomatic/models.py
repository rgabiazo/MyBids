"""
Domain-level data models shared across I/O, pipeline, and CLI layers.

The module provides:

* **Entity validators** (`SubjectID`, `SessionID`) that enforce minimal
  syntactic correctness for *sub-* / *ses-* identifiers.
* **`BIDSPath`** – a convenience wrapper that turns a fully rendered
  :class:`~bidscomatic.config.schema.BIDSEntities` object into an on-disk
  pathname while automatically skipping empty entities.
* Lightweight helper models (`SequenceRef`, `ScanPlan`) used as immutable
  transport objects between different pipeline stages.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import ClassVar, Iterable, List, Mapping, Optional

from pydantic import BaseModel

from bidscomatic.config.schema import BIDSEntities, Sequence

# --------------------------------------------------------------------------- #
# logging
# --------------------------------------------------------------------------- #
log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 1 – ID validators
# --------------------------------------------------------------------------- #

_SUB_RE: ClassVar[re.Pattern[str]] = re.compile(r"^sub-[A-Za-z0-9]+$")
_SES_RE: ClassVar[re.Pattern[str]] = re.compile(r"^ses-[A-Za-z0-9]+$")


class SubjectID(str):
    """Typed alias that guarantees a valid ``sub-XXX`` string."""

    # Pydantic hook ---------------------------------------------------------
    @classmethod
    def __get_validators__(cls):
        """Yield Pydantic validators.

        This hook provides :meth:`validate` so that Pydantic can invoke it
        whenever ``SubjectID`` fields are processed.
        """
        yield cls.validate

    # --------------------------------------------------------------------- #
    @classmethod
    def validate(cls, v):  # type: ignore[override]
        """
        Ensure *v* matches the BIDS `sub-*` pattern.

        Args:
            v: Any object accepted by :class:`str`. Commonly a string or int.

        Returns:
            The validated value wrapped as ``SubjectID``.

        Raises:
            ValueError: If *v* does not match ``^sub-[A-Za-z0-9]+$``.
        """
        v = str(v)
        if not _SUB_RE.match(v):
            raise ValueError("SubjectID must match ^sub-[A-Za-z0-9]+$")
        return cls(v)


class SessionID(str):
    """
    Typed alias that guarantees either a valid ``ses-YYY`` string **or**
    ``None`` when sessions are absent.
    """

    @classmethod
    def __get_validators__(cls):
        """Yield Pydantic validators.

        Exposes :meth:`validate` so that Pydantic can check ``SessionID``
        values during model parsing.
        """
        yield cls.validate

    # --------------------------------------------------------------------- #
    @classmethod
    def validate(cls, v):  # type: ignore[override]
        """
        Validate *v* as a session identifier.

        * ``None``/empty/``"no-session"`` → interpreted as *no session*.
        * Otherwise must match ``^ses-[A-Za-z0-9]+$``.

        Args:
            v: The raw input value.

        Returns:
            A valid ``SessionID`` **or** ``None``.

        Raises:
            ValueError: If *v* is not one of the accepted spellings.
        """
        if v in (None, "", "no-session"):
            return None
        v = str(v)
        if not _SES_RE.match(v):
            raise ValueError("SessionID must match ^ses-[A-Za-z0-9]+$")
        return cls(v)


# --------------------------------------------------------------------------- #
# 2 – Path helper
# --------------------------------------------------------------------------- #

class BIDSPath(BaseModel, frozen=True):
    """
    Compose a valid on-disk BIDS path from pre-rendered entities.

    Attributes
    ----------
    root
        Dataset root directory (e.g. ``/data/my-study``).
    datatype
        BIDS data-type folder such as ``anat``, ``func`` or ``dwi``.
    entities
        Fully rendered :class:`~bidscomatic.config.schema.BIDSEntities`
        object. Placeholders **must already be resolved**.
    extension
        File extension. Defaults to ``.nii.gz`` but may be overridden
        by callers that need side-cars (``.json``) or other formats.
    """

    root: Path
    datatype: str
    entities: BIDSEntities
    extension: str = ".nii.gz"

    # --------------------------------------------------------------------- #
    # helpers
    # --------------------------------------------------------------------- #

    @staticmethod
    def _ensure_prefix(value: str, prefix: str) -> str:
        """
        Return *value* with *prefix* prepended unless the value is already
        prefixed or still contains an unresolved placeholder.

        Args:
            value: The raw entity string.
            prefix: Prefix string such as ``"sub-"`` or ``"ses-"``.

        Returns:
            The possibly modified *value*. No mutation occurs when *value*
            already starts with *prefix* or begins with ``"{"``.
        """
        if not value or value.startswith(prefix) or value.startswith("{"):
            return value
        out = f"{prefix}{value}"
        # DEBUG breadcrumb helps trace automatic fixes without polluting INFO.
        log.debug("[BIDSPath] auto-prefixed '%s' → '%s'", value, out)
        return out

    # --------------------------------------------------------------------- #
    # Derived properties
    # --------------------------------------------------------------------- #

    @property
    def filename(self) -> str:
        """
        Return the filename component (no directories).

        Entities whose value is empty (``''`` or ``None``) are skipped so
        fragments like ``ses-_`` never appear.

        Returns:
            A string such as ``sub-001_ses-01_task-rest_bold.nii.gz``.
        """
        parts = [
            f"{k}-{v}"
            for k, v in self.entities.as_pairs()
            if v not in {"", None, f"{{{k}}}"}
        ]
        parts.append(self.entities.suffix)
        return "_".join(parts) + self.extension

    # ------------------------------------------------------------------ #
    @property
    def path(self) -> Path:
        """
        Resolve the full path under *root*.

        Layout:
        ``<root>/sub-XXX[/ses-YYY]/<datatype>/<filename>``

        Returns:
            A fully qualified :class:`pathlib.Path`.
        """
        sub_dir = self._ensure_prefix(self.entities.sub, "sub-")
        segs = [self.root, sub_dir]

        if self.entities.ses and self.entities.ses != "{ses}":
            ses_dir = self._ensure_prefix(self.entities.ses, "ses-")
            segs.append(ses_dir)

        segs.append(self.datatype)
        return Path(*segs) / self.filename


# --------------------------------------------------------------------------- #
# 3 – Lightweight references & work-unit definitions
# --------------------------------------------------------------------------- #

class SequenceRef(BaseModel, frozen=True):
    """
    Immutable reference to one *sequence definition* inside **series.yaml**.

    Useful as a dictionary key or log token without dragging full objects
    around.

    Attributes
    ----------
    modality
        Top-level YAML key (``anatomical``, ``functional`` …).
    key
        Second-level entry (e.g. ``T1w``, ``task``).
    """

    modality: str
    key: str


class ScanPlan(BaseModel, frozen=True):
    """
    Immutable description of one intended scan conversion job.

    Attributes
    ----------
    ref
        A :class:`SequenceRef` pointing back to the YAML definition.
    bids_path
        Destination BIDS path (target of a move/copy operation).
    sequence_id
        Raw filename token used for discovery (e.g. ``"T1w"``).
    parameters
        Optional list of phase-encode directions or similar variants.
    source_dicom_dir
        Populated at run-time when the discovery phase resolves the concrete
        DICOM series directory. ``None`` until then.
    """

    ref: SequenceRef
    bids_path: BIDSPath
    sequence_id: str
    parameters: Optional[List[str]] = None
    source_dicom_dir: Optional[Path] = None     # resolved later


# --------------------------------------------------------------------------- #
# 4 – Helper: YAML tree → iterable[ScanPlan]
# --------------------------------------------------------------------------- #

def _iterate_pe(parameters: Optional[List[str]]) -> List[str | None]:
    """
    Expand the *parameters* list into explicit phase-encoding tokens.

    Args:
        parameters: The optional ``parameters`` field from a YAML sequence
            definition.

    Returns:
        ``['AP', 'PA']`` or ``[None]`` when no parameters are present.
    """
    return parameters or [None]


# Mapping from YAML modality to canonical datatype folder name
_MODALITY2DT = {
    "anatomical": "anat",
    "functional": "func",
    "diffusion":  "dwi",
    "fieldmap":   "fmap",
}


def build_scan_plans(
    cfg_modalities: Mapping[str, Mapping[str, Sequence]],
    root: Path,
    sub: SubjectID,
    ses: SessionID | None,
    *,
    task: str | None = None,
) -> Iterable["ScanPlan"]:
    """
    Generate an iterable of :class:`ScanPlan` objects for a single
    *subject/session* combination.

    This helper leaves **placeholder resolution** to the caller; *entities*
    must be fully rendered prior to use.

    Args:
        cfg_modalities: The ``modalities`` mapping from
            :class:`~bidscomatic.config.schema.ConfigSchema`.
        root: Dataset root directory.
        sub: Valid ``sub-*`` identifier.
        ses: Optional ``ses-*`` identifier. ``None`` when sessions are absent.
        task: Optional task name to inject into functional entities.

    Yields:
        :class:`ScanPlan` objects describing every permutation required by the
        YAML (e.g. both phase-encode directions for diffusion).
    """
    for modality, blocks in cfg_modalities.items():
        for key, seq in blocks.items():
            base_ents = seq.bids

            # Common substitutions applied to every entity table
            common_update: dict[str, str | None] = {"sub": sub, "ses": ses}

            if seq.label:
                common_update["label"] = seq.label
            if task and base_ents.task and "{task}" in base_ents.task:
                common_update["task"] = task

            for pe in _iterate_pe(seq.parameters):
                ent_update = common_update | ({"dir": pe} if pe else {})
                ents = base_ents.model_copy(deep=True, update=ent_update)

                datatype = getattr(base_ents, "datatype", None) or _MODALITY2DT.get(
                    modality, modality
                )

                yield ScanPlan(
                    ref=SequenceRef(modality=modality, key=key),
                    bids_path=BIDSPath(root=root, datatype=datatype, entities=ents),
                    sequence_id=seq.sequence_id,
                    parameters=seq.parameters,
                )
