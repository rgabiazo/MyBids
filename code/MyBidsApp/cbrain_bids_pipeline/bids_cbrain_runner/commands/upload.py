"""
Upload a subset of a local BIDS dataset to a CBRAIN-accessible SFTP server.

High-level algorithm
--------------------
1. **Validate** the requested sub-tree with the official *bids-validator*.
2. **Discover** all matching local files using wildcard *steps* (e.g.
   ``sub-* ses-* anat``) and build a mapping ``{path_tuple: [filenames]}``.
3. **Connect** to the target SFTP data provider defined in *servers.yaml*
   (password authentication – no keys).
4. **Synchronise** the remote tree:
   * Create any missing directories.
   * Compare local vs. remote files and upload those absent on the server.
5. **Register** the freshly uploaded top-level folders as *Userfiles* in
   CBRAIN (optional, controlled by *do_register*).
6. **Move** the registered userfiles to a different Data Provider
   (*move_provider*) when requested.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from ..utils.local_files import (
    local_build_path_tree,
    local_gather_all_matched_files,
)
from ..utils.compare import compare_local_remote_files
from ..utils.output import print_jsonlike_dict
from ..utils.filetypes import guess_filetype
from .bids_validator import bids_validator_cli, find_bids_root_upwards
from .sftp import sftp_connect_from_config, list_subdirs_and_files
from .data_providers import register_files_on_provider
from .userfiles import find_userfile_id_by_name_and_provider, update_userfile_group_and_move

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------#
# Public helpers                                                                #
# -----------------------------------------------------------------------------#
def upload_bids_and_sftp_files(
    cfg: Mapping[str, object],
    base_url: str,
    token: str,
    steps: Sequence[str],
    *,
    do_register: bool = False,
    dp_id: int | None = None,
    filetypes: List[str] | None = None,
    group_id: int | None = None,
    move_provider: int | None = None,
    timeout: float | None = None,
) -> None:
    """Synchronise part of a local BIDS tree with an SFTP provider.

    Args:
        cfg: Combined configuration dictionary returned by
            :func:`bids_cbrain_runner.api.config_loaders.get_sftp_provider_config`.
        base_url: CBRAIN portal root.
        token: ``cbrain_api_token`` used for subsequent REST-level actions.
        steps: Wildcard components (e.g. ``['sub-*', 'ses-*', 'anat']``) that
            identify a sub-tree relative to the dataset root.
        do_register: When **True**, call ``/data_providers/{id}/register`` for
            each *top-level* uploaded folder.
        dp_id: Target Data Provider ID for registration (required when
            *do_register* is enabled).
        filetypes: List of CBRAIN *file-type* strings (e.g. ``["BidsSubject"]``)
            matching *top-level* folders.  If **None**, defaults to one entry
            ``["BidsSubject"]``.
        group_id: Optional project (``Group``) ID assigned to new userfiles.
        move_provider: When set, move the registered userfiles to this provider
            via ``/userfiles/change_provider``.
        timeout: Optional HTTP timeout forwarded to registration helpers.

    Returns:
        None.  Progress and diagnostics are emitted via :pymod:`logging`.

    Notes:
        * Uploads **skip** files that already exist remotely (exact name match).
        * Directory creation is idempotent; missing components are created
          recursively, existing ones are left untouched.
        * All network interactions use password authentication only (Paramiko).
    """
    # ------------------------------------------------------------------#
    # Early sanity checks                                                #
    # ------------------------------------------------------------------#
    if not steps:
        logger.error("[UPLOAD] No wildcard steps provided.")
        return

    # ------------------------------------------------------------------#
    # 1. Validate BIDS integrity                                         #
    # ------------------------------------------------------------------#
    if not bids_validator_cli(steps):
        logger.error("[UPLOAD] BIDS validation failed – aborting upload.")
        return

    # ------------------------------------------------------------------#
    # 2. Build a map of local files to be considered for upload          #
    # ------------------------------------------------------------------#
    base_dir: str = os.getcwd()
    partial_path: str = os.path.join(base_dir, *steps)
    dataset_root: str | None = find_bids_root_upwards(partial_path)
    if dataset_root is None:
        logger.error("[UPLOAD] Could not locate dataset_description.json.")
        return

    local_tree: Dict[str, dict] = local_build_path_tree(
        dataset_root, steps, recurse_if_no_more_steps=True
    )
    local_map: Dict[Tuple[str, ...], List[str]] = local_gather_all_matched_files(local_tree)
    if not local_map:
        logger.info("[UPLOAD] No local paths matched %s", steps)
        return

    # Collect all top-level basenames for potential registration
    all_basenames = sorted({pt[0] for pt in local_map.keys() if pt})

    # ------------------------------------------------------------------#
    # 3. Establish SFTP connection                                       #
    # ------------------------------------------------------------------#
    ssh_client, sftp_client = sftp_connect_from_config(cfg)
    if not ssh_client or not sftp_client:
        logger.error("[UPLOAD] SFTP connection failed – aborting.")
        return

    newly_uploaded: Dict[str, List[str]] = {}

    try:
        # ------------------------------------------------------------------#
        # 3a. Iterate through every leaf directory                           #
        # ------------------------------------------------------------------#
        for path_tuple, local_files in local_map.items():
            top_folder = path_tuple[0] if path_tuple else None

            # Detect when *path_tuple* is a file name. In that case, upload it
            # relative to the dataset root instead of treating it as a
            # sub-directory.
            is_direct_file = os.path.isfile(os.path.join(dataset_root, *path_tuple))
            local_subpath = dataset_root if is_direct_file else os.path.join(dataset_root, *path_tuple)

            logger.info("[UPLOAD] Scanning local path: %s", local_subpath)

            # Ensure the remote directory structure mirrors the local path.
            if ensure_remote_dir_structure(sftp_client, path_tuple):
                logger.debug(
                    "[UPLOAD] Created remote directories: %s", "/".join(path_tuple)
                )

            # Build absolute remote path (root defaults to SFTP cwd or '/').
            remote_full_path: str = (
                sftp_client.getcwd() or "/"
                if is_direct_file
                else "/" + "/".join(path_tuple)
                if path_tuple
                else sftp_client.getcwd() or "/"
            )
            # List current remote contents.
            subdirs, existing_remote_files = list_subdirs_and_files(
                sftp_client, remote_full_path
            )

            # Emit comparison table (INFO level).
            compare_local_remote_files(
                local_path=local_subpath,
                local_files=local_files,
                remote_path=remote_full_path,
                remote_files=existing_remote_files,
            )

            # Determine which local files are absent remotely.
            missing_on_remote = set(local_files) - set(existing_remote_files)
            if not missing_on_remote:
                # No action required for this sub-folder.
                continue

            # ------------------------------------------------------------------#
            # 3b. Upload missing files                                           #
            # ------------------------------------------------------------------#
            for fname in missing_on_remote:
                if is_direct_file:
                    lpath = os.path.join(dataset_root, *path_tuple)
                    rpath = f"/{fname}"
                else:
                    lpath = os.path.join(local_subpath, fname)
                    rpath = f"{remote_full_path}/{fname}"

                logger.info("[UPLOAD] Uploading %s → %s", fname, rpath)
                try:
                    sftp_client.put(lpath, rpath)
                except Exception as exc:  # noqa: BLE001
                    logger.error("[UPLOAD] Failed to upload %s: %s", fname, exc)
                    continue

            if top_folder:
                newly_uploaded.setdefault(top_folder, []).extend(missing_on_remote)
    finally:
        # Always close the SFTP session to free network resources.
        sftp_client.close()
        ssh_client.close()

    # ------------------------------------------------------------------#
    # 4. Post-processing (optional registration & move)                 #
    # ------------------------------------------------------------------#
    if not newly_uploaded:
        logger.info("[UPLOAD] Nothing new was uploaded.")

    logger.info("[UPLOAD] Newly uploaded files (by top-level folder):")
    print_jsonlike_dict(newly_uploaded, "Uploaded Summary")

    # --------------------------------------------------------------#
    # 4a. Register uploaded folders as CBRAIN userfiles             #
    # --------------------------------------------------------------#
    if do_register:
        if dp_id is None:
            logger.warning(
                "[UPLOAD] --upload-register requested but --upload-dp-id missing."
                "  Registration skipped."
            )
            return

        basenames = list(newly_uploaded.keys()) if newly_uploaded else list(all_basenames)
        if filetypes is None:
            cb_types = [guess_filetype(b, cfg) for b in basenames]
        else:
            filetypes = filetypes or ["BidsSubject"]
            cb_types = [
                (filetypes[0] if len(filetypes) == 1 else filetypes[i])
                for i in range(len(basenames))
            ]

        logger.info(
            "[UPLOAD] Registering %d new userfiles on provider %d…",
            len(basenames),
            dp_id,
        )
        register_files_on_provider(
            base_url=base_url,
            token=token,
            provider_id=dp_id,
            basenames=basenames,
            types=cb_types,
            browse_path=None,
            as_user_id=None,
            other_group_id=group_id,
            timeout=timeout,
        )

        # ----------------------------------------------------------#
        # 4b. Optionally move the userfiles to another provider     #
        # ----------------------------------------------------------#
        if move_provider:
            for folder in basenames:
                uf_id = find_userfile_id_by_name_and_provider(
                    base_url,
                    token,
                    folder,
                    dp_id,
                    timeout=timeout,
                )
                if not uf_id:
                    logger.warning(
                        "[UPLOAD] Could not locate newly registered userfile %r.", folder
                    )
                    continue

                logger.info(
                    "[UPLOAD] Moving userfile %d (%s) → provider %d",
                    uf_id,
                    folder,
                    move_provider,
                )
                update_userfile_group_and_move(
                    base_url=base_url,
                    token=token,
                    userfile_id=uf_id,
                    new_group_id=None,
                    new_provider_id=move_provider,
                    timeout=timeout,
                )


# -----------------------------------------------------------------------------#
# Internal utilities                                                            #
# -----------------------------------------------------------------------------#
def ensure_remote_dir_structure(
    sftp_client,
    path_tuple: Tuple[str, ...],
) -> bool:
    """Create *path_tuple* recursively on the SFTP server if absent.

    Behaviour change
    ----------------
    If the **final component** looks like an actual file (``"." in name`` **and**
    the file exists locally), it is *ignored* for directory creation.  This
    allows commands such as::

        cbrain-cli --upload-bids-and-sftp-files dataset_description.json …

    to place the JSON at ``/dataset_description.json`` instead of creating a
    directory of that name.

    Args
    ----
    sftp_client
        Active :class:`paramiko.SFTPClient` instance.
    path_tuple
        Positional components relative to the SFTP root
        (e.g. ``('sub-001', 'ses-01', 'anat')``).

    Returns
    -------
    bool
        ``True`` if **any** directory was created, otherwise ``False``.
    """
    import os

    created_any  = False
    current_path = "/"
    sftp_client.chdir("/")

    # ----------------------------------------------------------#
    # Detect “filename” final token and drop it from mkdir loop  #
    # ----------------------------------------------------------#
    if path_tuple:
        last_part = path_tuple[-1]
        if "." in last_part:
            local_probe = os.path.join(os.getcwd(), *path_tuple)
            if os.path.isfile(local_probe):
                # Treat last element as a file – exclude from dir-creation.
                path_tuple = path_tuple[:-1]

    # ----------------------------------------------------------#
    # Create / verify each remaining directory component         #
    # ----------------------------------------------------------#
    for part in path_tuple:
        next_path = os.path.join(current_path, part).replace("\\", "/")
        try:
            # Fast path – directory already exists.
            sftp_client.stat(next_path)
            sftp_client.chdir(next_path)
            current_path = next_path
            continue
        except FileNotFoundError:
            # Needs creation; fall through.
            pass

        try:
            sftp_client.mkdir(next_path)
            created_any = True
            sftp_client.chdir(next_path)
            current_path = next_path
        except Exception as exc:  # noqa: BLE001
            logger.error("[UPLOAD] Could not mkdir %r: %s", next_path, exc)
            return created_any

    return created_any

