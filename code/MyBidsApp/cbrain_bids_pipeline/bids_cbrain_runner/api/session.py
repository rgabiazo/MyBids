"""
Session-management helpers for authenticating against a CBRAIN portal.

The CBRAIN REST API supports either an explicit ``cbrain_api_token`` query
parameter **or** a username / password POST to ``/session``.  This module
abstracts token retrieval and renewal so that the rest of the package never
needs to worry about session state.

Public helpers
--------------
create_session
    Perform a username/password login and return a fresh API token.
ensure_token
    Re-use an existing token if valid, otherwise fetch a new one and
    optionally persist it to disk.

All functions raise :class:`CBRAINAuthError` for *expected* authentication
failures (e.g. missing credentials).  Network-level issues surface unchanged
as :class:`requests.exceptions.RequestException` to allow the CLI to decide
how aggressively to retry.
"""

from __future__ import annotations

import logging
import os
from typing import Dict

import requests
import yaml

from .client import cbrain_get

logger = logging.getLogger(__name__)


class CBRAINAuthError(Exception):
    """Raised when no valid token can be obtained."""


# ----------------------------------------------------------------------
# Low-level login
# ----------------------------------------------------------------------
def create_session(base_url: str, username: str, password: str) -> str:
    """Return a freshly-minted ``cbrain_api_token`` obtained via POST /session.

    Args:
        base_url: Root URL of the CBRAIN portal (no trailing slash required).
        username: Portal username (often an institutional email).
        password: Portal password.

    Returns:
        The token string to be supplied as the ``cbrain_api_token`` query
        parameter in subsequent requests.

    Raises:
        requests.exceptions.HTTPError: If the HTTP status is not 2xx.
        RuntimeError: If the JSON response lacks a ``token`` field.
    """
    url = f"{base_url.rstrip('/')}/session"
    data = {"login": username, "password": password}
    headers = {"Accept": "application/json"}

    resp = requests.post(url, headers=headers, data=data)
    resp.raise_for_status()

    payload = resp.json()
    token = payload.get("cbrain_api_token") or payload.get("token")
    if not token:
        raise RuntimeError(f"Unexpected session response: {payload}")

    logger.info("Retrieved new CBRAIN token for user %r", username)
    return token


# ----------------------------------------------------------------------
# Token helper used by the CLI
# ----------------------------------------------------------------------
def ensure_token(
    *,
    base_url: str,
    cfg_path: str,
    cfg: Dict[str, str],
    force_refresh: bool = False,
    timeout: float | None = None,
) -> Dict[str, str]:
    """Return a valid token (re-using or refreshing as needed).

    The helper implements a **three-step** strategy:

    1.  If *force_refresh* is *False* and *cfg* already contains a token,
        validate it via ``GET /session``.
    2.  Otherwise attempt a username/password login **if** the environment
        provides ``CBRAIN_USERNAME`` and ``CBRAIN_PASSWORD``.
    3.  Optionally persist any freshly-acquired token back to *cfg_path* when
        the environment variable ``CBRAIN_PERSIST`` is set.

    Args:
        base_url: Root URL of the CBRAIN portal.
        cfg_path: Absolute path to *cbrain.yaml* (used only when persisting).
        cfg:      Parsed contents of *cbrain.yaml* **plus** any env overrides.
        force_refresh: When *True*, bypasses token validation and forces a new
            login even if *cfg* already contained a token.

    Returns:
        ``{"cbrain_api_token": <token>, "cbrain_base_url": <base_url>}``

    Raises:
        CBRAINAuthError: When no valid token is available and login
            credentials are missing.
        requests.exceptions.RequestException: For network-level errors.
    """
    token = None if force_refresh else cfg.get("cbrain_api_token")

    # ------------------------------------------------------------------
    # 1) Attempt to validate an existing token
    # ------------------------------------------------------------------
    if token:
        resp = cbrain_get(base_url, "session", token, timeout=timeout)
        if resp.status_code == 200:
            return {"cbrain_api_token": token, "cbrain_base_url": base_url}
        # Any status except 401 is unexpected → propagate upstream
        if resp.status_code != 401:
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # 2) Fall back to an explicit login
    # ------------------------------------------------------------------
    user = os.getenv("CBRAIN_USERNAME")
    pwd = os.getenv("CBRAIN_PASSWORD")
    if not (user and pwd):
        raise CBRAINAuthError(
            "No valid token and CBRAIN_USERNAME/PASSWORD not supplied"
        )

    new_token = create_session(base_url, user, pwd)

    # ------------------------------------------------------------------
    # 3) Optionally persist the new token to disk
    # ------------------------------------------------------------------
    if os.getenv("CBRAIN_PERSIST"):
        try:
            disk_cfg: Dict[str, str] = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, encoding="utf-8") as stream:
                    disk_cfg = yaml.safe_load(stream) or {}
            disk_cfg["cbrain_api_token"] = new_token

            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            with open(cfg_path, "w", encoding="utf-8") as stream:
                yaml.safe_dump(disk_cfg, stream)
        except Exception:  # noqa: BLE001 – best-effort persistence
            logger.warning("Could not write new token to %s", cfg_path)

    return {"cbrain_api_token": new_token, "cbrain_base_url": base_url}
