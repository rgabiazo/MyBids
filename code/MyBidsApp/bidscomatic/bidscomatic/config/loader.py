"""
YAML configuration loader.

This helper locates, reads, merges, and validates *series.yaml* and
*files.yaml* before returning a :class:`bidscomatic.config.schema.ConfigSchema`
instance.

Search precedence for **each** YAML (first match wins)
1. An explicit path argument (``--series`` / ``--files`` on the CLI).
2. ``<dataset>/code/config/<name>.yaml`` – project-local override.
3. The packaged default shipped inside the wheel.

All resolution logic is concentrated here so the rest of *bidscomatic*
treats configuration as an already-validated object.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import warnings
import yaml
from importlib.resources import as_file, files

from .schema import ConfigSchema

# --------------------------------------------------------------------------- #
# Wheel-internal fallbacks (work even from a zipped wheel)                    #
# --------------------------------------------------------------------------- #
try:
    _DEFAULT_SERIES = files("bidscomatic.resources") / "default_series.yaml"
    _DEFAULT_FILES = files("bidscomatic.resources") / "default_files.yaml"
except ModuleNotFoundError:
    _BASE = Path(__file__).resolve().parent.parent / "resources"
    _DEFAULT_SERIES = _BASE / "default_series.yaml"
    _DEFAULT_FILES = _BASE / "default_files.yaml"

# --------------------------------------------------------------------------- #
# Helper functions                                                            #
# --------------------------------------------------------------------------- #


def _dataset_local(root: Optional[str | Path], name: str) -> Optional[Path]:
    """Return ``<root>/code/config/<name>`` or *None* if *root* is ``None``.

    Args:
        root: Dataset root supplied by the caller.
        name: YAML filename (e.g. ``"series.yaml"``).

    Returns:
        Path pointing at the dataset-local YAML or ``None`` when *root*
        is ``None`` so no local override is possible.
    """
    if root is None:
        return None
    return Path(root).expanduser().resolve() / "code" / "config" / name


def _first_existing(*candidates: Optional[Path]) -> Optional[Path]:
    """Return the first path in *candidates* that exists on disk.

    Args:
        *candidates: Arbitrary number of paths, each of which may be
            ``None`` or non-existent.

    Returns:
        The first existing path or ``None`` when none of them exist.
    """
    for p in candidates:
        if p is not None and p.exists():
            return p
    return None


def _load_yaml(path: Path) -> dict:
    """Read a YAML file.

    Args:
        path: Location of the YAML document.

    Returns:
        Dictionary parsed from the file, or an empty dict if the file is empty.
    """
    return yaml.safe_load(path.read_text()) or {}


def _resolve_yaml(
    explicit: Optional[Path],
    dataset_root: Optional[Path],
    fname: str,
    fallback: Path,
) -> Path:
    """Resolve a YAML path for *fname* according to the documented precedence.

    Args:
        explicit: Absolute path supplied by the caller (may be ``None``).
        dataset_root: Root of the BIDS dataset (may be ``None``).
        fname: Plain filename (``"series.yaml"`` / ``"files.yaml"``).
        fallback: Packaged default used when no other candidate exists.

    Returns:
        Path to the YAML that should be loaded.
    """
    resolved = _first_existing(explicit, _dataset_local(dataset_root, fname))
    if resolved is None:
        with as_file(fallback) as p:
            resolved = p
    return resolved


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def load_config(
    *,
    series_path: Optional[str | Path] = None,
    files_path: Optional[str | Path] = None,
    dataset_root: Optional[str | Path] = None,
) -> ConfigSchema:
    """Return a fully validated :class:`ConfigSchema`.

    The function merges *series.yaml* (required) and *files.yaml* (optional)
    before passing the combined document through Pydantic validation.

    Args:
        series_path: Explicit path to *series.yaml*. ``None`` triggers the
            search sequence described in the module doc-string.
        files_path: Explicit path to *files.yaml*. ``None`` triggers the same
            search sequence as above.
        dataset_root: Root of the BIDS dataset. Required when project-local
            overrides are expected.

    Returns:
        A :class:`ConfigSchema` object ready for downstream use.

    Raises:
        RuntimeError: When the merged YAML fails Pydantic validation.
    """
    dataset_root = Path(dataset_root).expanduser().resolve() if dataset_root else None
    series_path = Path(series_path).expanduser().resolve() if series_path else None
    files_path = Path(files_path).expanduser().resolve() if files_path else None

    # Resolve paths according to the documented precedence.
    series_yaml = _resolve_yaml(series_path, dataset_root, "series.yaml", _DEFAULT_SERIES)
    files_yaml = _resolve_yaml(files_path, dataset_root, "files.yaml", _DEFAULT_FILES)

    # ----------------------------- merge dicts ----------------------------- #
    merged: dict = _load_yaml(series_yaml)

    files_dict = _load_yaml(files_yaml)

    # ── A) legacy-wrapped style → unwrap once ───────────────────────────── #
    # Accept both::
    #   files:
    #     ignore: …
    # and the newer bare style::
    #   ignore: …
    if "files" in files_dict and not {"ignore", "rename"} & files_dict.keys():
        files_dict = files_dict["files"] or {}

    # ── B) bare style – already correct ─────────────────────────────────── #

    # ── C) typo / unknown keys – warn & ignore --------------------------- #
    if not {"ignore", "rename"} & files_dict.keys():
        if files_dict:  # non-empty yet unrecognised structure
            warnings.warn(
                f"{files_yaml} contains no 'ignore' or 'rename' section; "
                "rules were ignored.",
                UserWarning,
            )
        files_dict = {}

    merged["files"] = files_dict

    # ----------------------------- validate ------------------------------- #
    try:
        return ConfigSchema(**merged)
    except Exception as exc:  # pydantic.ValidationError or YAML issues
        raise RuntimeError(f"Invalid configuration – {exc}") from exc
