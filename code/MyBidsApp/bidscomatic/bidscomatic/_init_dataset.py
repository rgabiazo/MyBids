"""
Dataset-initialisation helpers shared by both the CLI and unit-tests.

This module creates (or overwrites) a minimal *dataset_description.json* and
optionally renames the dataset root directory so that the folder name matches
the *Name* field in a clean "slugified" form (ASCII and dashes; lower-case by
default).

Background
----------
The upstream implementation relied on *package data* available via
``importlib.resources``::

    files("bidscomatic.templates") / "dataset_description.json.j2"

When working from a source checkout that does not include the
``bidscomatic/templates`` directory, that call raises *FileNotFoundError*.
The fallback implemented here loads the template from a sibling ``templates/``
folder located next to this module, allowing editable installs or partial
copies to function without packaging the resources.

Public API
----------
initialise_dataset()
    Create or replace *dataset_description.json* and return the final root
    path (the original root may change when *rename_root* is requested).
"""
from __future__ import annotations

import json
from importlib.resources import read_text
from pathlib import Path
from typing import Optional

import jinja2
import structlog

from bidscomatic import __version__
from bidscomatic.utils.naming import rename_root_if_needed

log = structlog.get_logger()

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
_BIDS_VERSION_DEFAULT = "1.10.0"  # default BIDS specification version

# --------------------------------------------------------------------------- #
# Template loading
# --------------------------------------------------------------------------- #
# Attempt to read the template from installed package data.  If that fails
# (e.g. source checkout without package data), fall back to a neighbouring
# templates directory.
try:
    _TEMPLATE_SRC: str = read_text(
        "bidscomatic.templates", "dataset_description.json.j2"
    )
except (ModuleNotFoundError, FileNotFoundError):
    _TEMPLATE_SRC = (
        Path(__file__).with_name("templates") / "dataset_description.json.j2"
    ).read_text()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _render_dataset_json(
    *,
    name: str,
    dataset_type: str = "raw",
    authors: Optional[list[str]] = None,
    license: Optional[str] = None,
    acknowledgements: str = "",
    how_to_ack: str = "",
    funding: Optional[list[str]] = None,
    ethics_approvals: Optional[list[str]] = None,
    references_and_links: Optional[list[str]] = None,
    dataset_doi: Optional[str] = None,
    bids_version: str = _BIDS_VERSION_DEFAULT,
) -> str:
    """Return a pretty-printed *dataset_description.json* string.

    Args:
        name: Title of the study (BIDS *Name* field).
        dataset_type: Dataset category, normally ``"raw"`` or ``"derivative"``.
        authors: Optional list of author names.  An empty list yields the
            placeholder array defined in the template.
        license: Optional license identifier for the ``License`` field.
        acknowledgements: Text placed in ``Acknowledgements``.
        how_to_ack: Instructions for citing the dataset.
        funding: Optional list of funding strings.
        ethics_approvals: Optional list of REB identifiers.
        references_and_links: Optional list of related references or URLs.
        dataset_doi: Optional DOI string for ``DatasetDOI``.
        bids_version: Version tag placed in the ``BIDSVersion`` field.

    Returns:
        str: Formatted JSON string ready to be written to disk.
    """
    tpl = jinja2.Template(_TEMPLATE_SRC)
    raw_json = tpl.render(
        name=name,
        dataset_type=dataset_type,
        authors=authors or [],
        license=license,
        acknowledgements=acknowledgements,
        how_to_ack=how_to_ack,
        funding=funding or [],
        ethics_approvals=ethics_approvals or [],
        references_and_links=references_and_links or [],
        dataset_doi=dataset_doi,
        bids_version=bids_version,
        tool_version=__version__,
    )
    # Round-trip through json to guarantee valid, indented output.
    return json.dumps(json.loads(raw_json), indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def initialise_dataset(
    root: Path,
    *,
    name: str,
    authors: Optional[list[str]] = None,
    license: Optional[str] = None,
    acknowledgements: str = "",
    how_to_ack: str = "",
    funding: Optional[list[str]] = None,
    ethics_approvals: Optional[list[str]] = None,
    references_and_links: Optional[list[str]] = None,
    dataset_doi: Optional[str] = None,
    dataset_type: str = "raw",
    force: bool = False,
    rename_root: bool = True,
) -> Path:
    """Create or overwrite *dataset_description.json* inside *root*.

    Args:
        root: Target dataset root directory.  The directory is created if it
            does not exist.  When *rename_root* is ``True`` and *root* already
            exists, it may be renamed so that its basename equals a slugified
            version of *name*.
        name: Study title used for the *Name* field and, when *rename_root* is
            enabled, the source for the slugified folder name.
        authors: Optional list of author strings.
        license: Optional license identifier.
        acknowledgements: Text for ``Acknowledgements``.
        how_to_ack: Text for ``HowToAcknowledge``.
        funding: Optional list of funding strings.
        ethics_approvals: Optional list of REB identifiers.
        references_and_links: Optional list of related references or URLs.
        dataset_doi: Optional DOI string.
        dataset_type: Either ``"raw"`` or ``"derivative"``.
        force: When ``True`` an existing *dataset_description.json* is
            overwritten.  When ``False`` and the file exists,
            *FileExistsError* is raised.
        rename_root: Rename the *root* directory to match *name* if the current
            folder name differs.

    Returns:
        Path: The **final** dataset root path.  This may differ from the input
        *root* when *rename_root* triggers a rename.

    Raises:
        FileExistsError: *dataset_description.json* exists and *force* is
            ``False``.
    """
    # Optionally rename the root directory first so that subsequent operations
    # use the final path.
    if rename_root:
        root = rename_root_if_needed(root, name, logger=log)

    root.mkdir(parents=True, exist_ok=True)
    dd_json = root / "dataset_description.json"

    # Abort early unless overwriting is explicitly allowed.
    if dd_json.exists() and not force:
        raise FileExistsError(
            f"{dd_json} exists – pass '--force' (CLI) or force=True (API) to overwrite."
        )

    # Render and write the JSON file.
    dd_json.write_text(
        _render_dataset_json(
            name=name,
            dataset_type=dataset_type,
            authors=authors,
            license=license,
            acknowledgements=acknowledgements,
            how_to_ack=how_to_ack,
            funding=funding,
            ethics_approvals=ethics_approvals,
            references_and_links=references_and_links,
            dataset_doi=dataset_doi,
        )
    )
    log.info("Created %s", dd_json)
    return root


def update_dataset_description(
    root: Path,
    *,
    name: str | None = None,
    authors: Optional[list[str]] = None,
    license: str | None = None,
    acknowledgements: str | None = None,
    how_to_ack: str | None = None,
    funding: Optional[list[str]] = None,
    ethics_approvals: Optional[list[str]] = None,
    references_and_links: Optional[list[str]] = None,
    dataset_doi: str | None = None,
    dataset_type: str | None = None,
) -> None:
    """Update fields in an existing ``dataset_description.json``.

    Unknown keys are preserved.  Only the explicitly provided parameters are
    modified.

    Args:
        root: Dataset root containing ``dataset_description.json``.
        name: Optional new title for the ``Name`` field.
        authors: Optional list of author strings.  When ``None`` the field is
            left unchanged; an empty list clears it.
        license: Optional replacement for ``License``.
        acknowledgements: Optional replacement text for ``Acknowledgements``.
        how_to_ack: Optional replacement for ``HowToAcknowledge``.
        funding: Optional list of funding strings.
        ethics_approvals: Optional list of REB identifiers.
        references_and_links: Optional list of related references or URLs.
        dataset_doi: Optional replacement DOI.
        dataset_type: Optional replacement for ``DatasetType``.

    Raises:
        FileNotFoundError: When ``dataset_description.json`` does not exist.
    """

    dd_json = root / "dataset_description.json"
    if not dd_json.exists():
        raise FileNotFoundError(dd_json)

    with dd_json.open(encoding="utf-8") as fh:
        data = json.load(fh)

    if name is not None:
        data["Name"] = name
    if authors is not None:
        data["Authors"] = authors
    if license is not None:
        data["License"] = license
    if acknowledgements is not None:
        data["Acknowledgements"] = acknowledgements
    if how_to_ack is not None:
        data["HowToAcknowledge"] = how_to_ack
    if funding is not None:
        data["Funding"] = funding
    if ethics_approvals is not None:
        data["EthicsApprovals"] = ethics_approvals
    if references_and_links is not None:
        data["ReferencesAndLinks"] = references_and_links
    if dataset_doi is not None:
        data["DatasetDOI"] = dataset_doi
    if dataset_type is not None:
        data["DatasetType"] = dataset_type

    dd_json.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    log.info("Updated %s", dd_json)
