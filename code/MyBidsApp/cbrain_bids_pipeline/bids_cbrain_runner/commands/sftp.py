"""SFTP utilities for CBRAIN-BIDS pipelines.

This module centralises low-level SFTP interactions used by
``cbrain-cli`` (alias ``bids-cbrain-cli``).  Responsibilities include:

* Opening password-based Paramiko sessions given a provider configuration.
* Navigating wildcard directory patterns to list or recurse over files.
* Building nested dictionaries that mirror remote directory trees so they can
  be rendered in BIDS-style JSON.
* Convenience wrappers that pretty-print remote structures or constrain
  listings to a specific CBRAIN *group* (project).

All helpers accept plain Python data structures (e.g. dictionaries produced by
``get_sftp_provider_config``) and return standard collections so that
higher-level code stays decoupled from Paramiko internals.  Network resources
are closed deterministically to avoid descriptor leaks.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from typing import Dict, List, Sequence, Tuple

import paramiko

from ..utils.bids_style import to_bids_style
from ..utils.output import print_jsonlike_dict
from .userfiles import list_userfiles_by_group
from ..api.client_openapi import CbrainClient

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Core connection helpers
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Core connection helpers
# -----------------------------------------------------------------------------

def sftp_connect_from_config(cfg: Dict[str, str]):
    """Open an SFTP session based on ``cfg``.

    Credential priority:
        1. ``sftp_username`` / ``sftp_password`` keys in *cfg*
        2. ``username`` / ``password`` keys in *cfg* (portal login)
        3. ``CBRAIN_SFTP_USERNAME`` / ``CBRAIN_SFTP_PASSWORD`` environment
        4. ``CBRAIN_USERNAME`` / ``CBRAIN_PASSWORD`` environment

    **Banner timeout**
        The SSH banner wait time defaults to ~15 s. This limit can be extended
        via a ``banner_timeout`` key in *servers.yaml* or the environment
        variable ``CBRAIN_SFTP_BANNER_TIMEOUT``.

    Args:
        cfg: Dictionary from
            :func:`bids_cbrain_runner.api.config_loaders.get_sftp_provider_config`.

    Returns:
        Tuple ``(ssh_client, sftp_client)`` where each element may be ``None`` on
        failure.
    """
    hostname: str | None = cfg.get("host")
    port: int = cfg.get("port", 22)

    # ── Credentials (priority list) ──────────────────────────────────────────
    username: str | None = (
        cfg.get("sftp_username")
        or cfg.get("username")
        or os.getenv("CBRAIN_SFTP_USERNAME")
        or os.getenv("CBRAIN_USERNAME")
    )
    password: str | None = (
        cfg.get("sftp_password")
        or cfg.get("password")
        or os.getenv("CBRAIN_SFTP_PASSWORD")
        or os.getenv("CBRAIN_PASSWORD")
    )

    if not hostname or not username or not password:
        logger.error(
            "[SFTP] Missing host, username or password.  Provide credentials via\n"
            "        – config file (*servers.yaml*)\n"
            "        – environment CBRAIN_[SFTP_]USERNAME/PASSWORD."
        )
        return None, None

    # ── Banner-timeout resolution (YAML → env-var → default) ────────────────
    banner_timeout: int | float = (
        cfg.get("banner_timeout")                  # servers.yaml
        or int(os.getenv("CBRAIN_SFTP_BANNER_TIMEOUT", "60"))
    )

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.debug(
            "[SFTP] Connecting to %s:%s as %s  (banner_timeout=%s)",
            hostname, port, username, banner_timeout
        )
        ssh_client.connect(
            hostname,
            port=port,
            username=username,
            password=password,
            banner_timeout=banner_timeout,      # <-- timeout
        )
    except Exception as exc:
        logger.error(
            "[SFTP] Could not connect to %s:%s as %s: %s",
            hostname, port, username, exc
        )
        return None, None

    sftp_client = ssh_client.open_sftp()
    logger.debug("[SFTP] Connection established, SFTP client opened.")
    return ssh_client, sftp_client



# -----------------------------------------------------------------------------
# Directory listing utilities
# -----------------------------------------------------------------------------

def list_subdirs_and_files(
    sftp_client: paramiko.SFTPClient,
    directory: str,
) -> Tuple[List[str], List[str]]:
    """Return immediate sub‑directories and files under *directory*.

    The function performs a single `listdir` followed by `stat` on each entry to
    discriminate between files and directories.

    Args:
        sftp_client: Active Paramiko SFTP client.
        directory: Absolute remote path.

    Returns:
        tuple[list[str], list[str]]: Sorted lists ``(subdirs, files)``.
        Empty lists are returned when the path is missing or unreadable.
    """
    try:
        contents = sftp_client.listdir(directory)
    except FileNotFoundError:
        logger.error("[SFTP] Directory not found: %s", directory)
        return [], []
    except Exception as exc:
        logger.error("[SFTP] Could not listdir '%s': %s", directory, exc)
        return [], []

    subdirs: List[str] = []
    files: List[str] = []

    for entry in contents:
        full = os.path.join(directory, entry)
        try:
            st = sftp_client.stat(full)
            # ``S_ISDIR`` equivalent without importing stat module.
            if st.st_mode & 0o040000:
                subdirs.append(entry)
            else:
                files.append(entry)
        except Exception:
            # Fall back to treating unknown entries as files.
            files.append(entry)

    return sorted(subdirs), sorted(files)


# -----------------------------------------------------------------------------
# Recursive helpers used by higher‑level commands
# -----------------------------------------------------------------------------

def _recurse_for_all_files(
    sftp_client: paramiko.SFTPClient,
    current_dir: str,
    partial_path: Sequence[str],
    final_map: Dict[str, List[str]],
) -> None:
    """Depth‑first traversal collecting *all* files under *current_dir*.

    Builds *final_map* where keys are path fragments relative to the
    traversal root (joined by ``/``) and values are lists of file names.
    """
    subdirs, files = list_subdirs_and_files(sftp_client, current_dir)
    final_map["/".join(partial_path)] = files

    for sd in subdirs:
        new_dir = os.path.join(current_dir, sd)
        _recurse_for_all_files(sftp_client, new_dir, partial_path + [sd], final_map)


# -----------------------------------------------------------------------------
# Public API – navigate and list helpers
# -----------------------------------------------------------------------------

def navigate_and_list_files(
    cfg: Dict[str, str],
    steps: Sequence[str],
    *,
    recurse_remaining: bool = False,
) -> List[str] | None:
    """Follow *steps* on the remote tree and list files.

    Each element in *steps* is interpreted as a shell‑style wildcard pattern.
    The function descends into the first directory that matches the current
    pattern.  At the final level it either lists files directly or, when
    *recurse_remaining* is ``True``, returns every file under that subtree.

    Args:
        cfg: SFTP connection details as for :pyfunc:`sftp_connect_from_config`.
        steps: Sequence like ``['sub-*', 'ses-*', 'anat']``.
        recurse_remaining: When ``True``, perform a full recursion after the
            final pattern is consumed; otherwise list files only at that depth.

    Returns:
        list[str] | None: Sorted unique file names.  ``None`` signals an SFTP
        connection problem; an empty list means no match found.
    """
    ssh_client, sftp_client = sftp_connect_from_config(cfg)
    if not ssh_client or not sftp_client:
        return None

    try:
        current_dir = sftp_client.getcwd() or "/"

        # Consume each wildcard pattern sequentially.
        for step in steps:
            subdirs, files = list_subdirs_and_files(sftp_client, current_dir)
            matched_subdirs = [sd for sd in subdirs if fnmatch.fnmatch(sd, step)]
            matched_files = [f for f in files if fnmatch.fnmatch(f, step)]

            if not matched_subdirs and not matched_files:
                logger.info("[SFTP] No directory/file matches '%s' under %s", step, current_dir)
                return []

            # When files match the current pattern, return them immediately –
            # the search terminates at this point.
            if matched_files:
                logger.debug("[SFTP] Found file(s) matching step '%s' under %s: %s", step, current_dir, matched_files)
                return matched_files

            # Otherwise select the first matching directory and continue.
            chosen = matched_subdirs[0]
            next_dir = os.path.join(current_dir, chosen)
            try:
                sftp_client.chdir(next_dir)
            except Exception as exc:
                logger.warning("[SFTP] Could not chdir to %s: %s", next_dir, exc)
                return []
            current_dir = sftp_client.getcwd() or next_dir

        # All patterns have been consumed – decide on depth of listing.
        if recurse_remaining:
            final_map: Dict[str, List[str]] = {}
            _recurse_for_all_files(sftp_client, current_dir, steps, final_map)
            combined: List[str] = []
            for files in final_map.values():
                combined.extend(files)
            all_files = combined
        else:
            _, all_files = list_subdirs_and_files(sftp_client, current_dir)

        return sorted(set(all_files))

    finally:
        # Always close the SFTP session to avoid leaking sockets.
        sftp_client.close()
        ssh_client.close()


# -----------------------------------------------------------------------------
# Tree‑building helpers reused by CLI pretty‑printers
# -----------------------------------------------------------------------------

def build_sftp_path_tree(
    sftp_client: paramiko.SFTPClient,
    start_dir: str,
    steps: Sequence[str],
):
    """Construct a nested dictionary mirroring the remote directory tree.

    The returned structure is suitable for conversion with
    :pyfunc:`bids_cbrain_runner.utils.bids_style.to_bids_style`.
    """
    tree: Dict[str, Dict] = {}
    _walk_sftp_tree(sftp_client, start_dir, steps, 0, [], tree)
    return tree


def _walk_sftp_tree(
    sftp_client: paramiko.SFTPClient,
    current_dir: str,
    steps: Sequence[str],
    step_index: int,
    partial_path: List[str],
    tree: Dict[str, Dict],
):
    """Recursive helper used by :pyfunc:`build_sftp_path_tree`."""
    # Base‑case: every pattern has been matched – recurse into *all* children.
    if step_index >= len(steps):
        _walk_all_remaining_sftp(sftp_client, current_dir, partial_path, tree)
        return

    pattern = steps[step_index]
    subdirs, files = list_subdirs_and_files(sftp_client, current_dir)

    matched_subdirs = [sd for sd in subdirs if fnmatch.fnmatch(sd, pattern)]
    matched_files = [f for f in files if fnmatch.fnmatch(f, pattern)]

    if not matched_subdirs and not matched_files:
        logger.debug("No matches for pattern '%s' in %s", pattern, current_dir)
        return

    # Register matching files as leaf nodes.
    for mf in matched_files:
        path_dict = {"_files": [mf], "_subdirs": []}
        _insert_subdict(tree, partial_path + [mf], path_dict)

    # Recurse into each matching directory.
    for match in matched_subdirs:
        next_dir = os.path.join(current_dir, match)
        _walk_sftp_tree(
            sftp_client,
            next_dir,
            steps,
            step_index + 1,
            partial_path + [match],
            tree,
        )


def _walk_all_remaining_sftp(
    sftp_client: paramiko.SFTPClient,
    dir_path: str,
    path_parts: List[str],
    tree: Dict[str, Dict],
):
    """After all patterns matched, record every file and directory below."""
    subdirs, files = list_subdirs_and_files(sftp_client, dir_path)
    _insert_path(tree, path_parts, subdirs, files)

    for sd in subdirs:
        new_dir = os.path.join(dir_path, sd)
        _walk_all_remaining_sftp(sftp_client, new_dir, path_parts + [sd], tree)


def _insert_subdict(tree: Dict[str, Dict], path_parts: Sequence[str], subdict: Dict):
    """Insert ``subdict`` at ``path_parts`` inside ``tree``.

    Creates parent dictionaries as needed.
    """
    current = tree
    for part in path_parts[:-1]:
        current = current.setdefault(part, {})
    current[path_parts[-1]] = subdict


def _insert_path(
    tree: Dict[str, Dict],
    path_parts: Sequence[str],
    subdirs: Sequence[str],
    files: Sequence[str],
):
    """Ensure node exists then set its ``_subdirs`` and ``_files`` keys."""
    current = tree
    for part in path_parts:
        current = current.setdefault(part, {})
    current["_files"] = list(files)
    current["_subdirs"] = list(subdirs)


# -----------------------------------------------------------------------------
# Convenience wrappers used by the CLI – pretty‑print directory trees
# -----------------------------------------------------------------------------

def sftp_cd_steps(cfg: Dict[str, str], steps: Sequence[str]) -> None:
    """Connect via SFTP, match *steps*, and pretty‑print the resulting tree."""
    ssh_client, sftp_client = sftp_connect_from_config(cfg)
    if not ssh_client or not sftp_client:
        return

    try:
        start_dir = sftp_client.getcwd() or "/"
        sftp_tree = build_sftp_path_tree(sftp_client, start_dir, steps)
        bids_dict = to_bids_style(sftp_tree)
        if bids_dict:
            print_jsonlike_dict(bids_dict, "Found matching directory structure on SFTP")
        else:
            logger.info("\nNo matching directory structure found on SFTP for steps: %s\n", steps)
    finally:
        sftp_client.close()
        ssh_client.close()


def sftp_cd_steps_with_group(
    cfg: Dict[str, str],
    base_url: str,
    token: str,
    group_id: int,
    steps: Sequence[str],
) -> None:
    """List directories via :pyfunc:`sftp_cd_steps`, restricted to a group.

    Only include userfiles that belong to ``group_id``.
    """
    ssh_client, sftp_client = sftp_connect_from_config(cfg)
    if not ssh_client or not sftp_client:
        return

    try:
        start_dir = sftp_client.getcwd() or "/"
        sftp_tree = build_sftp_path_tree(sftp_client, start_dir, steps)

        # Retrieve valid top‑level names for the requested project.
        client = CbrainClient(base_url, token)
        group_files = list_userfiles_by_group(client, group_id, per_page=500)
        allowed = {uf["name"] for uf in group_files}

        # Remove any remote directories not present in the group.
        for key in list(sftp_tree):
            if key not in allowed:
                logger.info("[SFTP‑GROUP] Skipping %r; not in group %d", key, group_id)
                del sftp_tree[key]

        bids_dict = to_bids_style(sftp_tree)
        if bids_dict:
            print_jsonlike_dict(bids_dict, "Found the matching group on SFTP")
        else:
            logger.info("\nNo matching directory structure for group=%d steps=%s\n", group_id, steps)
    finally:
        sftp_client.close()
        ssh_client.close()
