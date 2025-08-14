"""Configuration file loaders and helpers.

This module centralises logic for reading *YAML* configuration files that
control CBRAIN-BIDS pipelines.  Three independent domains are covered:

1. **CBRAIN credentials and session parameters** – ``load_cbrain_config``
2. **Infrastructure metadata** (*servers*, *tools*) – ``load_servers_config``,
   ``get_sftp_provider_config``, ``load_tools_config``
3. **Pipeline defaults and override files** – ``load_pipeline_config``

Each loader returns plain ``dict`` objects so that calling code can remain
framework-agnostic.  All YAML parsing uses :pymod:`yaml.safe_load` to
eliminate the risk of executing arbitrary objects.

Functions follow a *fail-soft* philosophy: configuration files that are
missing or malformed lead to **empty** dictionaries with informative log
messages rather than hard crashes, enabling graceful degradation in CLI
applications.

Note:
    Dot-prefixed helper keys such as ``_deep_update`` are kept private to
    reduce the public surface area.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# 1) CBRAIN-specific configuration helpers
# ────────────────────────────────────────────────────────────────────────────
def load_cbrain_config(config_dir: str | None = None) -> Dict[str, Any]:
    """Return a CBRAIN configuration dictionary.

    Lookup order:
        1. *cbrain.yaml* on disk (optional)
        2. Environment variables (``CBRAIN_*``) – override disk values
        3. Automatic login via :func:`bids_cbrain_runner.api.session.create_session`
           if no valid token is present but *username* / *password* are available

    Args:
        config_dir: Directory containing *cbrain.yaml*.  If *None*, defaults to
            the bundled ``config`` folder that ships with *bids_cbrain_runner*.

    Returns:
        ``dict`` with keys such as ``cbrain_api_token``, ``cbrain_base_url``,
        ``username``, ``password`` …
    """
    from .session import create_session  # local import avoids circular deps

    if config_dir is None:
        config_dir = os.path.join(os.path.dirname(__file__), "config")
    cfg_path = os.path.join(config_dir, "cbrain.yaml")

    # --------------------------------------------------------------------- #
    # 1.  Load on-disk YAML (if present)                                    #
    # --------------------------------------------------------------------- #
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as fh:
            cfg: Dict[str, Any] = yaml.safe_load(fh) or {}
    else:
        cfg = {}

    # --------------------------------------------------------------------- #
    # 2.  Overlay CBRAIN_* environment variables                            #
    # --------------------------------------------------------------------- #
    env_map = {
        "cbrain_api_token": "CBRAIN_API_TOKEN",
        "username": "CBRAIN_USERNAME",
        "password": "CBRAIN_PASSWORD",
        "sftp_username": "CBRAIN_SFTP_USERNAME",
        "sftp_password": "CBRAIN_SFTP_PASSWORD",
    }
    for key, env in env_map.items():
        val = os.getenv(env)
        if val:
            cfg[key] = val

    # --------------------------------------------------------------------- #
    # 3.  Automatic session creation when credentials are available         #
    # --------------------------------------------------------------------- #
    base_url = cfg.get("cbrain_base_url", "https://portal.cbrain.mcgill.ca")
    needs_login = (
        not cfg.get("cbrain_api_token")
        and cfg.get("username")
        and cfg.get("password")
    )
    if needs_login:
        try:
            new_token = create_session(
                base_url=base_url,
                username=cfg["username"],
                password=cfg["password"],
            )
            cfg["cbrain_api_token"] = new_token

            # Persist the new token when CBRAIN_PERSIST=1
            if os.getenv("CBRAIN_PERSIST"):
                os.makedirs(config_dir, exist_ok=True)
                with open(cfg_path, "w", encoding="utf-8") as stream:
                    yaml.safe_dump(cfg, stream)
        except Exception as exc:  # noqa: BLE001 – logging handled below
            logger.warning("CBRAIN auto-login failed: %s", exc)

    return cfg


def load_servers_config(config_dir: str | None = None) -> Dict[str, Any]:
    """Read *servers.yaml* and return its contents.

    Args:
        config_dir: Folder that hosts *servers.yaml*.  Falls back to the
            internal ``config`` directory when *None*.

    Returns:
        Dictionary with top-level keys ``cbrain_base_url`` and
        ``data_providers``.  An empty dict is returned when the file is absent
        or unreadable.
    """
    if config_dir is None:
        config_dir = os.path.join(os.path.dirname(__file__), "config")

    servers_path = os.path.join(config_dir, "servers.yaml")
    if not os.path.exists(servers_path):
        logger.warning("servers.yaml not found at %s; returning empty dict.", servers_path)
        return {}

    with open(servers_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_sftp_provider_config(provider_name: str = "sftp_1") -> Dict[str, Any]:
    """Extract SFTP credentials for *provider_name* from *servers.yaml*.

    Args:
        provider_name: Key under ``data_providers`` whose details should be
            merged with the global ``cbrain_base_url``.

    Returns:
        Flat dictionary containing ``host``, ``port``, ``cbrain_id`` and any
        other fields defined for the provider.  Missing keys result in an
        empty dict.
    """
    servers = load_servers_config()
    cfg: Dict[str, Any] = {}

    # Global CBRAIN URL is useful in many CLI contexts.
    if "cbrain_base_url" in servers:
        cfg["cbrain_base_url"] = servers["cbrain_base_url"]

    provider = servers.get("data_providers", {}).get(provider_name, {})
    cfg.update(provider)
    return cfg


def get_sftp_provider_config_by_id(provider_id: int) -> Dict[str, Any]:
    """Return SFTP credentials for a provider by ``cbrain_id``.

    Args:
        provider_id: Numeric ``cbrain_id`` listed in ``servers.yaml``.

    Returns:
        Dictionary merged with the global ``cbrain_base_url``. Returns an empty
        mapping when no matching entry exists.
    """
    servers = load_servers_config()
    cfg: Dict[str, Any] = {}

    if "cbrain_base_url" in servers:
        cfg["cbrain_base_url"] = servers["cbrain_base_url"]

    for prov in servers.get("data_providers", {}).values():
        if prov.get("cbrain_id") == provider_id:
            cfg.update(prov)
            break

    return cfg


def load_tools_config(config_dir: str | None = None) -> Dict[str, Any]:
    """Load *tools.yaml* and return the nested ``tools`` section.

    Args:
        config_dir: Directory containing *tools.yaml*.  Defaults to the
            built-in ``config`` sub-folder.

    Returns:
        Mapping of tool-name → configuration dictionary.  Returns an empty dict
        when the file is missing or malformed.
    """
    if config_dir is None:
        config_dir = os.path.join(os.path.dirname(__file__), "config")

    tools_path = os.path.join(config_dir, "tools.yaml")
    if not os.path.exists(tools_path):
        logger.warning("tools.yaml not found at %s; returning empty dict.", tools_path)
        return {}

    with open(tools_path, "r", encoding="utf-8") as fh:
        full_yaml = yaml.safe_load(fh) or {}
    return full_yaml.get("tools", {})

# ────────────────────────────────────────────────────────────────────────────
# 2) Pipeline-level configuration (defaults + user override)
# ────────────────────────────────────────────────────────────────────────────
def load_pipeline_config() -> Dict[str, Any]:
    """Return the deep-merged pipeline configuration.

    Merge strategy:
        * **Package defaults** – ``defaults.yaml`` bundled with the package
        * **User override**  – ``<BIDS_ROOT>/code/config/config.yaml``
        The override is *deep-merged* onto the defaults so that only modified
        keys need to appear in the external file.

    Returns:
        Combined configuration dictionary.  When no BIDS root is detected or
        the override file is absent, the defaults are returned verbatim.  The
        resulting mapping always exposes ``roots["derivatives_root"]`` as well
        as a top-level ``derivatives_root`` entry for backward compatibility.
    """
    merged: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # 1. load defaults from the installed package                        #
    # ------------------------------------------------------------------ #
    here = os.path.dirname(__file__)  # points to …/api
    default_path = os.path.join(here, "config", "defaults.yaml")
    try:
        with open(default_path, "r", encoding="utf-8") as fh:
            defaults: Dict[str, Any] = yaml.safe_load(fh) or {}
        merged.update(defaults)
        logger.info("Loaded defaults from %s", default_path)
    except FileNotFoundError:
        logger.error("Could not read defaults.yaml at %s", default_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to parse defaults.yaml: %s", exc)

    # ------------------------------------------------------------------ #
    # 2. discover BIDS root to locate external override                  #
    # ------------------------------------------------------------------ #
    from bids_cbrain_runner.commands.bids_validator import find_bids_root_upwards

    dataset_root = find_bids_root_upwards(os.getcwd())
    if not dataset_root:
        logger.error("Could not locate BIDS root (dataset_description.json).")
        return merged

    # External config path under project tree
    override_path = os.path.join(dataset_root, "code", "config", "config.yaml")
    if os.path.exists(override_path):
        logger.info("Applying external override from %s", override_path)
        try:
            with open(override_path, "r", encoding="utf-8") as fh:
                user_cfg: Dict[str, Any] = yaml.safe_load(fh) or {}
            _deep_update(merged, user_cfg)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to merge override %s: %s", override_path, exc)
    else:
        logger.info("No external config found at %s; using defaults only", override_path)

    # ------------------------------------------------------------------ #
    # 3. expose both roots["derivatives_root"] and top-level key         #
    # ------------------------------------------------------------------ #
    deriv_root = (
        merged.get("roots", {}).get("derivatives_root")
        or merged.get("derivatives_root")
        or "derivatives"
    )
    merged.setdefault("roots", {})["derivatives_root"] = deriv_root
    merged["derivatives_root"] = deriv_root

    return merged


# ────────────────────────────────────────────────────────────────────────────
# 3) Private helpers
# ────────────────────────────────────────────────────────────────────────────
def _deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge *override* into *base*.

    Dict values that are themselves dictionaries are merged **in-place**; all
    other types are overwritten by the value in *override*.

    Args:
        base: Destination dictionary that is mutated in place.
        override: Source dictionary whose keys take precedence.

    Returns:
        The mutated *base* dict (returned for convenience).
    """
    for key, val in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(val, dict)
        ):
            _deep_update(base[key], val)
        else:
            base[key] = val
    return base
