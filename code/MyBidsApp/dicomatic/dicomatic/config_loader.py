"""
YAML configuration loader for *dicomatic* with multi‑path credential lookup.

Search order for the secrets file (first hit wins):

1. Path specified via the ``DICOMATIC_SECRETS_FILE`` environment variable.
2. ``<package_root>/code/.secrets/uwo_credentials`` (historical default).
3. ``<BIDS_root>/.secrets/uwo_credentials`` if a BIDS dataset is detected.
   ``find_bids_root`` locates the dataset root (folder containing
   ``dataset_description.json``); ``dicomatic`` will look for
   ``<BIDS_root>/.secrets/uwo_credentials``—for example
   ``MyBids/.secrets/uwo_credentials``.
4. ``$(pwd)/.secrets/uwo_credentials`` relative to the current process.

A valid secrets file contains **exactly two non‑blank lines**: the
username followed by the password. Missing or malformed files are treated as
non‑fatal; the loader falls back to credentials in the YAML configuration
followed by interactive prompts later in the workflow.

The module keeps the original public function ``load_config`` unchanged in
signature and return type. Only comment style and credential discovery logic
are updated.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional, Iterable

from ruamel.yaml import YAML

# Keys that must remain plain dictionaries to preserve downstream behaviour
RAW_DICTS = {
    "dicom_tag_map",
    "dicom_query_tags",
    "study_params",
    "session_map",
}

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def _to_ns(obj: Any, *, key: Optional[str] = None) -> Any:
    """Recursively convert dictionaries to :class:`types.SimpleNamespace`.

    Args:
        obj: Arbitrary Python object obtained from the parsed YAML file.
        key: Current parent‑level key. Used to skip conversion for entries
            listed in :data:`RAW_DICTS`.

    Returns:
        ``SimpleNamespace`` objects for dictionaries, lists of converted
        objects for lists, or the original value for all other types.
    """
    if isinstance(obj, dict):
        if key in RAW_DICTS:
            return obj  # Preserve specific dictionaries intact

        ns = SimpleNamespace()
        for k, v in obj.items():
            setattr(ns, k, _to_ns(v, key=k))
        return ns

    if isinstance(obj, list):
        return [_to_ns(v, key=key) for v in obj]

    return obj  # Primitive scalar remains untouched


def _candidate_secret_paths() -> Iterable[Path]:
    """Yield credential file paths in priority order.

    Paths are yielded without performing existence checks.

    Yields:
        Path objects that may contain credentials.
    """
    # 1. Explicit override via environment variable
    env_override = os.getenv("DICOMATIC_SECRETS_FILE")
    if env_override:
        yield Path(env_override).expanduser()

    # 2. Historical default: three directories above this file then /.secrets
    pkg_root = Path(__file__).resolve().parents[2] / ".secrets" / "uwo_credentials"
    yield pkg_root

    # 3. Secrets directory inside the nearest BIDS project root (folder with
    #    dataset_description.json), if discoverable
    from dicomatic.utils.project_root import find_bids_root  # Local import avoids cycle

    try:
        bids_root = Path(find_bids_root())
        yield bids_root / ".secrets" / "uwo_credentials"
    except RuntimeError:
        pass  # No BIDS dataset detected; skip this candidate

    # 4. Working directory of the current process
    yield Path.cwd() / ".secrets" / "uwo_credentials"


def _load_credentials() -> tuple[str | None, str | None]:
    """Return ``(username, password)`` from the first valid secrets file.

    A secrets file is considered valid when it contains **at least two**
    non‑blank lines. Additional lines are ignored.

    Returns:
        Tuple of username and password; ``(None, None)`` if no valid file is
        found or an error occurs while reading.
    """
    for path in _candidate_secret_paths():
        if not path.is_file():
            continue
        try:
            lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
            if len(lines) >= 2:
                log.debug("Loaded credentials from %s", path)
                return lines[0], lines[1]
            log.warning("Secrets file %s must contain at least two non‑blank lines", path)
        except Exception as exc:  # noqa: BLE001 – broad except acceptable for IO
            log.warning("Could not read secrets file %s: %s", path, exc)
    return None, None


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> SimpleNamespace:
    """Load YAML configuration, merge credentials, and return a namespace tree.

    Args:
        config_path: Optional explicit YAML path. When ``None`` the default
            ``config/config.yaml`` relative to the package directory is used.

    Returns:
        Configuration tree where nested dictionaries are converted to
        ``SimpleNamespace`` objects, except for keys defined in
        :data:`RAW_DICTS`.

    Raises:
        FileNotFoundError: Raised when the YAML configuration file is absent.
    """
    # Resolve configuration file path
    cfg_file = Path(config_path).expanduser() if config_path else Path(__file__).with_name("config") / "config.yaml"

    if not cfg_file.is_file():
        raise FileNotFoundError(f"Configuration file not found at {cfg_file}")

    # Parse YAML into a raw Python structure
    yaml = YAML()
    with cfg_file.open("r", encoding="utf-8") as stream:
        raw_cfg: dict[str, Any] = yaml.load(stream)

    # Attempt to overlay credentials from secrets
    username, password = _load_credentials()
    if username and password:
        raw_cfg.setdefault("dicom", {})
        raw_cfg["dicom"]["username"] = username
        raw_cfg["dicom"]["password"] = password
    else:
        log.debug("No secrets file detected; relying on YAML or interactive prompts")

    # Convert to SimpleNamespace hierarchy while preserving certain raw dicts
    return _to_ns(raw_cfg)
