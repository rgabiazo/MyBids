"""
Light-weight HTTP helpers for interacting with the CBRAIN REST API.

Only the low-level mechanics of *sending* a request belong here; no higher-level
parsing or business logic is performed.  These helpers are used throughout the
package to keep request construction (base URL, headers, authentication token)
consistent and in one place.

All helpers return the raw ``requests.Response`` object so that callers can
decide how to handle status-codes, JSON decoding, pagination, retries, etc.

Functions
---------
cbrain_get
    Perform a token-authenticated ``GET`` request.
cbrain_post
    Perform a token-authenticated ``POST`` request, supporting form-data,
    multipart uploads and JSON bodies.
cbrain_put
    Perform a token-authenticated ``PUT`` request for resource updates.
cbrain_delete
    Perform a token-authenticated ``DELETE`` request.
"""

import os
from typing import Any, Dict, Optional

import requests

DEFAULT_TIMEOUT = 60.0


def _default_timeout() -> Optional[float]:
    """Return the timeout configured via ``CBRAIN_TIMEOUT`` or ``DEFAULT_TIMEOUT``."""
    env = os.getenv("CBRAIN_TIMEOUT")
    if not env:
        return DEFAULT_TIMEOUT
    try:
        return float(env)
    except ValueError:
        return DEFAULT_TIMEOUT


def cbrain_get(
    base_url: str,
    endpoint: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    timeout: Optional[float] = None,
) -> requests.Response:
    """Send a GET request to the CBRAIN API.

    Args:
        base_url: Fully-qualified root URL of the CBRAIN portal
            (e.g. ``"https://portal.cbrain.mcgill.ca"``).
        endpoint: Relative path under ``base_url`` without a leading slash
            (e.g. ``"groups/42"`` or ``"userfiles"``).
        token: The ``cbrain_api_token`` string obtained from a session.
        params: Additional query parameters to include in the URL.

    Returns:
        The raw :class:`requests.Response` object.
    """
    params = params or {}
    # The token must always be supplied as a query parameter.
    params["cbrain_api_token"] = token

    headers = {"Accept": "application/json"}
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    # No exception handling here; let callers decide how to react.
    if timeout is None:
        timeout = _default_timeout()

    return requests.get(url, headers=headers, params=params, timeout=timeout)


def cbrain_post(
    base_url: str,
    endpoint: str,
    token: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> requests.Response:
    """Send a POST request to the CBRAIN API.

    The helper supports the three most common request bodies encountered
    when working with CBRAIN:

    * ``data``  – for URL-encoded or multipart form payloads
    * ``files`` – for file uploads via multipart/form-data
    * ``json``  – for JSON payloads

    Args:
        base_url: Root URL of the CBRAIN portal.
        endpoint: Endpoint relative to ``base_url``.
        token: ``cbrain_api_token`` string.
        data: Form fields as a mapping from key to value.
        files: Mapping used by :pymod:`requests` to stream files.
        json: A JSON-serialisable Python mapping.

    Returns:
        The raw :class:`requests.Response` object.
    """
    params = {"cbrain_api_token": token}
    headers = {"Accept": "application/json"}
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    if timeout is None:
        timeout = _default_timeout()

    return requests.post(
        url,
        headers=headers,
        params=params,
        data=data,
        files=files,
        json=json,
        timeout=timeout,
    )


def cbrain_put(
    base_url: str,
    endpoint: str,
    token: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> requests.Response:
    """Send a PUT request to the CBRAIN API.

    Args:
        base_url: Root URL of the CBRAIN portal.
        endpoint: Endpoint relative to ``base_url``.
        token: ``cbrain_api_token`` string.
        data: Optional form-encoded payload.
        json: Optional JSON payload.
        allow_redirects: Whether ``requests`` should automatically follow
            HTTP redirects.

    Returns:
        The raw :class:`requests.Response` object.
    """
    params = {"cbrain_api_token": token}
    headers = {"Accept": "application/json"}
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    if timeout is None:
        timeout = _default_timeout()

    return requests.put(
        url,
        headers=headers,
        params=params,
        data=data,
        json=json,
        timeout=timeout,
    )


def cbrain_delete(
    base_url: str,
    endpoint: str,
    token: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
    allow_redirects: bool = True,
) -> requests.Response:
    """Send a DELETE request to the CBRAIN API.

    Args:
        base_url: Root URL of the CBRAIN portal.
        endpoint: Endpoint relative to ``base_url``.
        token: ``cbrain_api_token`` string.
        data: Optional form-encoded payload.
        json: Optional JSON payload.
        allow_redirects: Whether ``requests`` should automatically follow
            HTTP redirects.

    Returns:
        The raw :class:`requests.Response` object.
    """
    params = {"cbrain_api_token": token}
    headers = {"Accept": "application/json"}
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    if timeout is None:
        timeout = _default_timeout()

    return requests.delete(
        url,
        headers=headers,
        params=params,
        data=data,
        json=json,
        timeout=timeout,
        allow_redirects=allow_redirects,
    )
