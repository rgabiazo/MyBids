"""
Helpers for interacting with CBRAIN *groups* (projects).

The helpers now rely on :class:`bids_cbrain_runner.api.client_openapi.CbrainClient`
to perform OpenAPI requests.  Output is still returned as plain Python
objects so that calling code can format or log as required.
"""

from __future__ import annotations

import logging
import re

from ..api.client import cbrain_get
from ..api.client_openapi import ApiException, CbrainClient

_VALID_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")

logger = logging.getLogger(__name__)


def list_groups(
    base_url: str,
    token: str,
    page: int = 1,
    per_page: int = 100,
    *,
    timeout: float | None = None,
):
    """Retrieve an iterable of all groups visible to *token*.

    Args:
        base_url: CBRAIN portal URL.
        token: Valid API token with permission to list projects.
        page: Page number for server-side pagination.
        per_page: Items requested per page.

    Returns:
        ``list[dict]`` — Each entry is a CBRAIN *Group* JSON object.
        An empty list is returned on HTTP or parsing errors.
    """
    client = CbrainClient(base_url, token)
    try:
        groups = client.list_groups(
            page=page, per_page=per_page, timeout=timeout
        )
    except ApiException as exc:
        logger.error("Could not fetch groups: %s", exc)
        return []

    return [grp.to_dict() for grp in groups]


def describe_group(
    base_url: str,
    token: str,
    group_id: int,
    *,
    timeout: float | None = None,
) -> None:
    """Print a human-readable summary of a single CBRAIN group.

    Args:
        base_url: CBRAIN portal URL.
        token: API token.
        group_id: Numeric *id* of the group to describe.

    Side Effects:
        Writes formatted information to ``stdout``.
    """
    endpoint = f"groups/{group_id}"
    resp = cbrain_get(base_url, endpoint, token, timeout=timeout)
    if resp.status_code == 200:
        data = resp.json()
        print("Group details:")
        print(" ID:", data["id"])
        print(" Name:", data["name"])
        print(" Description:", data.get("description"))
        print(" Site ID:", data.get("site_id"))
        print(" Invisible:", data.get("invisible"))
    else:
        logger.error(
            "Could not describe group %d: HTTP %d – %s",
            group_id,
            resp.status_code,
            resp.text,
        )


def describe_group_userfiles(
    base_url: str,
    token: str,
    group_id: int,
    *,
    timeout: float | None = None,
):
    """Return userfiles associated with *group_id*.

    Args:
        base_url: CBRAIN portal URL.
        token: API token.
        group_id: Numeric group identifier.

    Returns:
        ``list[dict]`` containing userfiles with keys ``id``, ``name`` and
        ``type``.  An empty list is returned (and error logged) if the REST
        call fails.
    """
    endpoint = "userfiles"
    params = {"group_id": group_id, "per_page": 100}
    resp = cbrain_get(base_url, endpoint, token, params=params, timeout=timeout)
    if resp.status_code != 200:
        logger.error(
            "Could not fetch userfiles for group %d: HTTP %d – %s",
            group_id,
            resp.status_code,
            resp.text,
        )
        return []

    data = resp.json()
    # Keep only the minimal keys often used downstream.
    return [uf for uf in data if {"id", "name", "type"} <= uf.keys()]


def create_group(
    base_url: str,
    token: str,
    name: str,
    description: str | None = None,
    *,
    per_page: int = 100,
    timeout: float | None = None,
    ) -> dict | None:
    """Create a new project (group) on CBRAIN if the name is unused.

    The helper validates *name*, checks for existing groups with the same
    name and issues a ``POST /groups`` request when appropriate.

    Args:
        base_url: CBRAIN portal URL.
        token: Valid API token with permission to create projects.
        name: Desired project name. Only ``A–Z``, ``a–z``, ``0–9``, ``-``, ``_``
            and spaces are allowed.
        description: Optional free‑form description.
        per_page: Pagination size used when checking for existing groups.

    Returns:
        The JSON object describing the newly created group on success, or
        ``None`` if creation failed or the name already exists.
    """

    if not _VALID_NAME_RE.match(name):
        logger.error("Invalid group name '%s'", name)
        return None

    client = CbrainClient(base_url, token)

    # Check every page of /groups to ensure no project with the same name
    page = 1
    while True:
        try:
            existing = client.list_groups(
                page=page, per_page=per_page, timeout=timeout
            )
        except ApiException as exc:
            logger.error("Could not fetch groups: %s", exc)
            return None
        for grp in existing:
            if getattr(grp, "name", None) == name:
                logger.error(
                    "Group '%s' already exists with ID %s",
                    name,
                    getattr(grp, "id", "?"),
                )
                return None
        if len(existing) < per_page:
            break
        page += 1

    try:
        created = client.create_group(name, description=description, timeout=timeout)
    except ApiException as exc:
        logger.error("Could not create group '%s': %s", name, exc)
        return None

    logger.info("Created group '%s' with ID %s", created.name, created.id)
    return created.to_dict() if hasattr(created, "to_dict") else vars(created)


def find_group_id_by_name(
    base_url: str,
    token: str,
    name: str,
    *,
    per_page: int = 100,
    timeout: float | None = None,
) -> int | None:
    """Return the numeric group ID for ``name`` if it exists.

    The helper iterates through ``/groups`` pages until the requested name is
    found or the end of the listing is reached.
    """

    page = 1
    while True:
        groups = list_groups(
            base_url, token, page=page, per_page=per_page, timeout=timeout
        )
        for grp in groups:
            if grp.get("name") == name:
                return int(grp["id"])
        if len(groups) < per_page:
            break
        page += 1
    logger.error("Group '%s' not found", name)
    return None


def resolve_group_id(
    base_url: str,
    token: str,
    identifier: int | str | None,
    *,
    per_page: int = 100,
    timeout: float | None = None,
) -> int | None:
    """Coerce ``identifier`` (ID or name) to a numeric group ID."""

    if identifier is None:
        return None

    if isinstance(identifier, int):
        client = CbrainClient(base_url, token)
        try:
            client.groups_api.groups_id_get(identifier, _request_timeout=timeout)
            return identifier
        except ApiException:
            return None

    try:
        gid = int(identifier)
    except (TypeError, ValueError):
        return find_group_id_by_name(
            base_url,
            token,
            str(identifier),
            per_page=per_page,
            timeout=timeout,
        )

    client = CbrainClient(base_url, token)
    
    try:
        client.groups_api.groups_id_get(gid, _request_timeout=timeout)
        return gid
    except ApiException:
        return None

