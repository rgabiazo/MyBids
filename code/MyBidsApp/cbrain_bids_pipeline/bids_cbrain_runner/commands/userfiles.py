"""High-level helpers for querying and manipulating *Userfile* records.

This module provides small, stateless wrappers around the REST-level helpers
(:pymod:`bids_cbrain_runner.api.client`) to keep the CLI implementation tidy.
All functions **log** results instead of returning rich objects because the
surrounding command-line interface is intended for fast inspection rather than
library-style consumption.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

from ..api.client import cbrain_post, cbrain_put
from ..api.client_openapi import ApiException, CbrainClient

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------#
# Pagination helpers                                                            #
# -----------------------------------------------------------------------------#
def fetch_all_userfiles(
    client: CbrainClient,
    per_page: int = 100,
    *,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Retrieve **all** userfiles visible to the session.

    Args:
        client:  Authenticated :class:`CbrainClient` instance.
        per_page: Page size for the REST pagination mechanism.

    Returns:
        A list of raw JSON dictionaries exactly as returned by the API.
    """
    all_files: List[Dict[str, object]] = []
    page_num: int = 1

    while True:
        # Internal pagination; avoid cluttering DEBUG logs with noisy updates
        try:
            page_data = client.list_userfiles(
                page=page_num, per_page=per_page, timeout=timeout
            )
            page_files = [
                uf.to_dict() if hasattr(uf, "to_dict") else uf for uf in page_data
            ]
        except ApiException as exc:
            logger.error("Could not fetch userfiles (page %d): %s", page_num, exc)
            break

        all_files.extend(page_files)

        if len(page_files) < per_page:
            break

        page_num += 1

    return all_files


# -----------------------------------------------------------------------------#
# Convenience list filters                                                      #
# -----------------------------------------------------------------------------#
def list_userfiles(
    client: CbrainClient,
    per_page: int = 100,
    *,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Return every userfile accessible to the session."""
    return fetch_all_userfiles(
        client, per_page=per_page, timeout=timeout
    )


def list_userfiles_by_group(
    client: CbrainClient,
    group_id: int,
    per_page: int = 100,
    *,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Filter userfiles by **project** (group) ID."""
    files = fetch_all_userfiles(
        client, per_page=per_page, timeout=timeout
    )
    return [uf for uf in files if uf["group_id"] == group_id]


def list_userfiles_by_provider(
    client: CbrainClient,
    provider_id: int,
    per_page: int = 100,
    *,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Filter userfiles by **Data Provider** ID."""
    files = fetch_all_userfiles(
        client, per_page=per_page, timeout=timeout
    )
    return [uf for uf in files if uf["data_provider_id"] == provider_id]


def list_userfiles_by_group_and_provider(
    client: CbrainClient,
    group_id: int,
    provider_id: int,
    per_page: int = 100,
    *,
    timeout: float | None = None,
) -> List[Dict[str, object]]:
    """Filter userfiles by *both* project and provider IDs."""
    files = fetch_all_userfiles(
        client, per_page=per_page, timeout=timeout
    )
    return [
        uf
        for uf in files
        if uf["group_id"] == group_id and uf["data_provider_id"] == provider_id
    ]


# -----------------------------------------------------------------------------#
# Descriptive utilities                                                         #
# -----------------------------------------------------------------------------#
def describe_userfile(
    client: CbrainClient,
    userfile_id: int,
    *,
    timeout: float | None = None,
) -> None:
    """Print a one-page summary for a specific *Userfile*.

    Args:
        client: Authenticated :class:`CbrainClient`.
        userfile_id: Numeric identifier for the userfile.
    """
    try:
        uf = client.get_userfile(userfile_id, timeout=timeout)
        data = uf.to_dict() if hasattr(uf, "to_dict") else uf
    except ApiException as exc:
        print("[ERROR] Could not describe userfile:", exc)
        return

    print("Userfile details:")
    print(" ID:", data["id"])
    print(" Name:", data["name"])
    print(" Type:", data["type"])
    print(" Group:", data["group_id"])
    print(" Provider:", data["data_provider_id"])
    print(" Owner:", data["user_id"])


def find_userfile_id_by_name_and_provider(
    client: CbrainClient,
    filename: str,
    provider_id: int,
    *,
    timeout: float | None = None,
) -> Optional[int]:
    """Locate a userfile ID by *name* plus *provider*.

    Args:
        client: Authenticated :class:`CbrainClient`.
        filename: Exact ``name`` field of the userfile (e.g. ``"sub-001"``).
        provider_id: Data Provider ID hosting the file.

    Returns:
        The numeric userfile ID if found, otherwise **None**.
    """
    files = fetch_all_userfiles(client, per_page=500, timeout=timeout)
    for uf in files:
        if uf.get("name") == filename and uf.get("data_provider_id") == provider_id:
            return uf.get("id")
    return None


# -----------------------------------------------------------------------------#
# Mutation helpers                                                              #
# -----------------------------------------------------------------------------#
def update_userfile_group_and_move(
    base_url: str,
    token: str,
    userfile_id: int,
    *,
    new_group_id: int | None = None,
    new_provider_id: int | None = None,
    timeout: float | None = None,
) -> None:
    """Change a userfile’s project and/or move it to another provider.

    The function performs up to two independent operations:

    1. **Group update** – ``PUT /userfiles/{id}`` to assign a new project
       (skipped when *new_group_id* is **None**).
    2. **Provider move** – ``POST /userfiles/change_provider`` to migrate the
       file’s physical storage (skipped when *new_provider_id* is **None**).

    Args:
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token``.
        userfile_id: Numeric userfile identifier.
        new_group_id: Destination project (group) ID.
        new_provider_id: Destination Data Provider ID.
    """
    # ------------------------------------------------------------------#
    # 1. Update group (project)                                          #
    # ------------------------------------------------------------------#
    if new_group_id is not None:
        logger.info(
            "Assigning userfile %d to group %d…",
            userfile_id,
            new_group_id,
        )
        payload = {"userfile": {"group_id": new_group_id}}
        endpoint = f"userfiles/{userfile_id}"
        resp = cbrain_put(
            base_url, endpoint, token, json=payload, timeout=timeout
        )
        if resp.status_code == 200:
            logger.info("Group assignment successful.")
        else:
            logger.error(
                "Could not assign userfile %d to group %d: HTTP %d %s",
                userfile_id,
                new_group_id,
                resp.status_code,
                resp.text,
            )

    # ------------------------------------------------------------------#
    # 2. Move to a different Data Provider                               #
    # ------------------------------------------------------------------#
    if new_provider_id is not None:
        logger.info(
            "Moving userfile %d → provider %d…", userfile_id, new_provider_id
        )
        move_payload = {
            "file_ids": [str(userfile_id)],  # API expects strings
            "data_provider_id_for_mv_cp": new_provider_id,
        }
        resp = cbrain_post(
            base_url,
            "userfiles/change_provider",
            token,
            json=move_payload,
            timeout=timeout,
        )
        if resp.status_code == 200:
            logger.info("Move initiated successfully.")
        else:
            logger.error(
                "Could not move userfile %d to provider %d: HTTP %d %s",
                userfile_id,
                new_provider_id,
                resp.status_code,
                resp.text,
            )


def delete_userfile(
    client: CbrainClient,
    userfile_id: int,
    *,
    dry_run: bool = False,
    timeout: float | None = None,
) -> None:
    """Delete a single userfile by numeric ID.

    The helper first queries ``/userfiles/{id}`` to retrieve the file name for
    logging purposes and then issues a ``DELETE`` request against the
    ``/userfiles/delete_files`` endpoint unless :pydata:`dry_run` is ``True``.

    Args:
        client: Authenticated :class:`CbrainClient`.
        userfile_id: Numeric identifier of the file to remove.
        dry_run: When ``True``, only log the intended deletion without
            contacting the server.
    """
    # Retrieve the file name so that logs are informative. Failure to fetch
    # metadata is not fatal; deletion may still proceed.
    name = None
    try:
        uf = client.get_userfile(userfile_id, timeout=timeout)
        name = uf.get("name") if isinstance(uf, dict) else getattr(uf, "name", None)
    except ApiException as exc:
        logger.error("Could not fetch metadata for userfile %d: %s", userfile_id, exc)

    if dry_run:
        logger.info("[DRY] Would delete %s (ID=%d)", name or "<unknown>", userfile_id)
        return


    try:
        client.delete_userfiles([userfile_id], timeout=timeout)
        logger.info("Deleted %s (ID=%d)", name or "userfile", userfile_id)
    except ApiException as exc:
        logger.error("Could not delete userfile %d: %s", userfile_id, exc)


def delete_userfiles_by_group_and_type(
    client: CbrainClient,
    group_id: int,
    filetypes: Sequence[str],
    *,
    per_page: int = 100,
    dry_run: bool = False,
    timeout: float | None = None,
) -> None:
    """Delete all userfiles within a project that match ``filetypes``."""
    files = list_userfiles_by_group(
        client, group_id, per_page=per_page, timeout=timeout
    )
    wanted = set(filetypes)
    targets = [uf for uf in files if uf.get("type") in wanted]

    type_list = ", ".join(filetypes)

    if not targets:
        logger.info("No userfiles of type(s) %s found in group %d", type_list, group_id)
        return

    logger.info(
        "Deleting %d userfile(s) of type(s) %s from group %d",
        len(targets),
        type_list,
        group_id,
    )

    for uf in targets:
        delete_userfile(
            client,
            int(uf.get("id")),
            dry_run=dry_run,
            timeout=timeout,
        )
