"""
High-level helpers for validating a local BIDS dataset and comparing it
against files on a remote SFTP data-provider registered in CBRAIN.

The public entry points focus on two scenarios:

* ``check_bids_and_sftp_files`` – validate a local BIDS directory, then
  compare every matching subfolder or file against the same path on the
  SFTP server.

* ``check_bids_and_sftp_files_with_group`` – same as above but filtered so
  that only local top-level folders present in a specific CBRAIN *group*
  (project) are considered.  This prevents uploading or comparing subjects
  that are not part of the project.

All routines assume that a valid *servers.yaml* entry exists for the SFTP
provider, and that authentication details can be resolved by
``sftp_connect_from_config`` (CBRAIN_SFTP_USERNAME / CBRAIN_SFTP_PASSWORD or
portal credentials).
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Tuple

from .bids_validator import bids_validator_cli, find_bids_root_upwards
from ..utils.local_files import (
    local_build_path_tree,
    local_gather_all_matched_files,
)
from .userfiles import list_userfiles_by_group
from ..api.client_openapi import CbrainClient
from .sftp import navigate_and_list_files
from ..utils.compare import compare_local_remote_files

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def check_bids_and_sftp_files_with_group(
    cfg: Dict[str, str],
    base_url: str,
    token: str,
    group_id: int,
    steps: List[str],
) -> None:
    """Validate BIDS and compare local vs. remote files for a specific project.

    Args:
        cfg: Merged configuration containing SFTP host, port, credentials and
            CBRAIN ``cbrain_api_token`` / ``cbrain_base_url`` keys.
        base_url: CBRAIN portal URL (e.g. ``https://portal.cbrain.mcgill.ca``).
        token: Valid CBRAIN API token with read access to *group_id*.
        group_id: Numeric CBRAIN group (project) identifier.
        steps: Sequence of wildcard patterns that define the sub-path to
            inspect (e.g. ``['sub-*', 'ses-*', 'anat']``).

    Notes:
        * Local BIDS validation is performed via the external *bids-validator*
          CLI.  Execution stops if critical errors are reported.
        * Only top-level local folders present **and** registered as userfiles
          in *group_id* **and** located on the same SFTP provider are checked.
    """
    valid = bids_validator_cli(steps)
    if not valid:
        logger.info("[CHECK-GROUP] BIDS validation failed. Stopping.")
        return

    # ------------------------------------------------------------------
    # Locate BIDS root relative to the first matching step
    # ------------------------------------------------------------------
    base_dir = os.getcwd()
    partial_path = os.path.join(base_dir, *steps)
    dataset_root = find_bids_root_upwards(partial_path)
    if not dataset_root:
        logger.info("[CHECK-GROUP] Could not find dataset root. Stopping.")
        return

    # ------------------------------------------------------------------
    # Build local file tree and collect leaf-level files
    # ------------------------------------------------------------------
    local_tree = local_build_path_tree(
        dataset_root,
        steps,
        recurse_if_no_more_steps=True,
    )
    local_map = local_gather_all_matched_files(local_tree)
    if not local_map:
        logger.info(
            "[CHECK-GROUP] No local subfolders/files found matching patterns: %s",
            steps,
        )
        return

    # ------------------------------------------------------------------
    # Retrieve userfiles belonging to the requested group
    # ------------------------------------------------------------------
    if not token:
        logger.warning(
            "[CHECK-GROUP] No cbrain_api_token, listing userfiles may fail."
        )
    client = CbrainClient(base_url, token)
    group_files = list_userfiles_by_group(
        client, group_id, per_page=500
    )
    userfiles_by_name: Dict[str, dict] = {uf["name"]: uf for uf in group_files}

    # The SFTP *provider* to which local uploads should map, derived from
    # *servers.yaml* (e.g. ``cbrain_id: 51``).
    sftp_provider_id = cfg.get("cbrain_id")
    if not sftp_provider_id:
        logger.warning(
            "[CHECK-GROUP] The config lacks a 'cbrain_id'; cannot confirm "
            "if userfile is on the same SFTP provider."
        )

    # ------------------------------------------------------------------
    # Filter local paths that are not in the group or not on the provider
    # ------------------------------------------------------------------
    local_top_level_keys = {
        pt[0] for pt in local_map.keys() if pt  # take the first path component
    }

    filtered_map: Dict[Tuple[str, ...], List[str]] = {}
    for path_tuple, local_files in local_map.items():
        if not path_tuple:  # root of dataset; skip
            continue
        top_dir = path_tuple[0]

        # Skip if not registered in this group
        if top_dir not in userfiles_by_name:
            logger.info(
                "[CHECK-GROUP] Local top-level folder '%s' is NOT in group %d. "
                "Skipping.",
                top_dir,
                group_id,
            )
            continue

        # Skip if userfile resides on a different data provider
        uf_obj = userfiles_by_name[top_dir]
        actual_provider = uf_obj.get("data_provider_id")
        if sftp_provider_id and actual_provider != sftp_provider_id:
            logger.info(
                "[CHECK-GROUP] Folder '%s' is in group %d but on provider=%s, "
                "not SFTP=%s. Skipping.",
                top_dir,
                group_id,
                actual_provider,
                sftp_provider_id,
            )
            continue

        # Keep the mapping if all checks pass
        filtered_map[path_tuple] = local_files

    if not filtered_map:
        logger.info(
            "[CHECK-GROUP] After filtering, no matching local paths remain "
            "for group %d on SFTP=%s.",
            group_id,
            sftp_provider_id,
        )
        _log_remote_subfolders_missing_locally(
            userfiles_by_name, local_top_level_keys, group_id, sftp_provider_id
        )
        return

    # ------------------------------------------------------------------
    # For each retained local subfolder, compare against remote SFTP
    # ------------------------------------------------------------------
    for path_tuple, local_files in filtered_map.items():
        local_subpath = os.path.join(dataset_root, *path_tuple)
        logger.info(
            "[CHECK-GROUP] Checking local path: %s, found %d files.",
            os.path.relpath(local_subpath, start=os.getcwd()),
            len(local_files),
        )

        remote_files = navigate_and_list_files(
            cfg, list(path_tuple), recurse_remaining=True
        )
        if remote_files is None:
            logger.warning(
                "[CHECK-GROUP] Could not connect to SFTP or other error. "
                "Skipping."
            )
            continue

        if len(remote_files) == 0:
            logger.info(
                "[CHECK-GROUP] No matching remote directory for %s "
                "(all local files missing on remote).",
                path_tuple,
            )

        compare_local_remote_files(
            local_path=local_subpath,
            local_files=local_files,
            remote_path="/".join(path_tuple),
            remote_files=remote_files,
        )

    # ------------------------------------------------------------------
    # Finally, report userfiles present remotely but absent locally
    # ------------------------------------------------------------------
    _log_remote_subfolders_missing_locally(
        userfiles_by_name, local_top_level_keys, group_id, sftp_provider_id
    )


def check_bids_and_sftp_files(cfg: Dict[str, str], steps: List[str]) -> None:
    """Validate a BIDS dataset and compare against the remote SFTP provider.

    Args:
        cfg: Combined configuration containing SFTP connection details.
        steps: Wildcard patterns defining the path to verify.

    Notes:
        This variant does **not** filter by CBRAIN group membership,
        so every local subfolder matched by *steps* is compared with the
        SFTP directory tree rooted at the provider’s base path.
    """
    valid = bids_validator_cli(steps)
    if not valid:
        return

    # Locate dataset root
    base_dir = os.getcwd()
    partial_path = os.path.join(base_dir, *steps)
    dataset_root = find_bids_root_upwards(partial_path)
    if not dataset_root:
        logger.info("[CHECK] Could not find dataset root. Stopping.")
        return

    # Build local path tree
    local_tree = local_build_path_tree(
        dataset_root, steps, recurse_if_no_more_steps=True
    )
    local_map = local_gather_all_matched_files(local_tree)
    if not local_map:
        logger.info(
            "[CHECK] No local subfolders/files found matching patterns: %s",
            steps,
        )
        return

    # Compare each local leaf directory against remote
    for path_tuple, local_files in local_map.items():
        local_subpath = os.path.join(dataset_root, *path_tuple)
        logger.info(
            "[CHECK] Checking local path: %s, found %d files.",
            os.path.relpath(local_subpath, start=os.getcwd()),
            len(local_files),
        )

        remote_files = navigate_and_list_files(
            cfg, list(path_tuple), recurse_remaining=True
        )
        if remote_files is None:
            logger.warning("[CHECK] Could not connect to SFTP or other error.")
            continue

        if len(remote_files) == 0:
            logger.info(
                "[CHECK] No matching remote directory for %s "
                "(all local files missing on remote).",
                path_tuple,
            )

        compare_local_remote_files(
            local_path=local_subpath,
            local_files=local_files,
            remote_path="/".join(path_tuple),
            remote_files=remote_files,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _log_remote_subfolders_missing_locally(
    userfiles_by_name: Dict[str, dict],
    local_top_level_keys: set[str],
    group_id: int,
    sftp_provider_id: int | None,
) -> None:
    """Report userfiles present on the provider but absent in the local tree.

    Args:
        userfiles_by_name: Mapping of *name → userfile-dict* from CBRAIN API.
        local_top_level_keys: Set containing each top-level folder found locally.
        group_id: CBRAIN project ID used for context in log messages.
        sftp_provider_id: ID of the SFTP provider being checked.

    The function prints INFO-level messages for every userfile that meets both
    of the following criteria:

    * ``data_provider_id`` matches *sftp_provider_id*.
    * The userfile’s ``name`` is **not** in *local_top_level_keys*.
    """
    if not sftp_provider_id:
        # Provider information unavailable; skip reporting.
        return

    for subname, uf in userfiles_by_name.items():
        # Skip userfiles on a different provider.
        if uf.get("data_provider_id") != sftp_provider_id:
            continue
        # Report only those not found locally.
        if subname not in local_top_level_keys:
            logger.info(
                "[CHECK-GROUP] Remote subject '%s' is in group %d "
                "(provider=%s) but NOT found locally.",
                subname,
                group_id,
                sftp_provider_id,
            )
