"""Upload a subset of a local BIDS dataset to a CBRAIN-accessible SFTP server.

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
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

from ..api.config_loaders import load_pipeline_config
from ..utils.compare import compare_local_remote_files
from ..utils.filetypes import guess_filetype
from ..utils.local_files import (
    local_build_path_tree,
    local_gather_all_matched_files,
)
from ..utils.output import print_jsonlike_dict
from ..utils.paths import (
    build_remote_path,
    infer_derivatives_root_from_steps,
    remap_path_tuple,
)
from ..utils.path_normalization import normalize_file_for_upload
from .bids_validator import bids_validator_cli, find_bids_root_upwards
from .data_providers import register_files_on_provider
from .sftp import list_subdirs_and_files, sftp_connect_from_config
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
    dry_run: bool = False,
    remote_root: str | None = None,
    path_map: Mapping[str, str] | None = None,
    rewrite_absolute_paths: bool = False,
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
        remote_root: Base directory on the SFTP server where files will be
            written. Defaults to the server root.
        path_map: Mapping of local trailing paths to remote replacements
            (e.g. ``{"anat": "ses-01/anat"}``).
        rewrite_absolute_paths: When True, inspect text files before upload
            and rewrite any embedded absolute paths into CBRAIN-friendly
            relative paths (see :mod:`bids_cbrain_runner.utils.path_normalization`).
            The original dataset on disk is left untouched; normalized copies
            are written into a temporary staging directory.
        dry_run: When **True**, skip actual uploads and registration.

    Returns:
        None.  Progress and diagnostics are emitted via :pymod:`logging`.
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

    pipeline_cfg = load_pipeline_config()
    derivatives_root = infer_derivatives_root_from_steps(steps, pipeline_cfg)
    # Avoid treating the target filename as part of the derivatives root
    if os.path.isfile(os.path.join(dataset_root, *steps)):
        derivatives_root = pipeline_cfg.get("derivatives_root", "derivatives")
    deriv_parts = Path(derivatives_root).parts
    pipeline_cfg = {
        **pipeline_cfg,
        "derivatives_root": derivatives_root,
        "roots": {**pipeline_cfg.get("roots", {}), "derivatives_root": derivatives_root},
    }

    dataset_root_path = Path(dataset_root).resolve()

    # Build the local path tree without falling back to recursive search when
    # a pattern component is missing. This avoids uploading unrelated folders
    # (e.g. ``func`` or ``fmap``) when a subject lacks the requested path
    # such as ``anat``.
    local_tree: Dict[str, dict] = local_build_path_tree(
        dataset_root, steps, recurse_if_no_more_steps=False
    )
    local_map: Dict[Tuple[str, ...], List[str]] = local_gather_all_matched_files(
        local_tree
    )

    # If the initial non-recursive scan only found files in the target
    # directory (e.g. ``dataset_description.json``) but that directory also
    # contains sub-folders, retry with recursion enabled so that the full
    # hierarchy is discovered.
    if (not local_map or set(local_map.keys()) == {tuple(steps)}) and local_tree:
        logger.debug(
            "[UPLOAD] Only top-level files found; retrying recursively"
        )
        local_tree = local_build_path_tree(
            dataset_root, steps, recurse_if_no_more_steps=True
        )
        local_map = local_gather_all_matched_files(local_tree)

    if not local_map:
        logger.info("[UPLOAD] No local paths matched %s", steps)
        return

    # Collect all potential registration targets
    all_targets: List[str] = []
    for pt in local_map.keys():
        if os.path.isfile(os.path.join(dataset_root, *pt)):
            all_targets.append("/".join(pt))
        elif pt:
            all_targets.append(pt[0])
    all_targets = sorted(set(all_targets))

    # Optional temporary root for normalized copies.
    temp_root: Path | None = None
    if rewrite_absolute_paths and not dry_run:
        temp_root = Path(
            tempfile.mkdtemp(
                prefix="cbrain-upload-normalized-",
                dir=dataset_root_path.parent,
            )
        )
        logger.info(
            "[NORMALIZE] Staging normalized copies with rewritten internal paths under %s",
            temp_root,
        )
    elif rewrite_absolute_paths and dry_run:
        logger.info(
            "[NORMALIZE] --upload-normalize-paths enabled (dry-run): "
            "will not modify files on disk; only report which would be rewritten."
        )

    # ------------------------------------------------------------------#
    # 3. Establish SFTP connection                                       #
    # ------------------------------------------------------------------#
    ssh_client, sftp_client = sftp_connect_from_config(cfg)
    if not ssh_client or not sftp_client:
        logger.error("[UPLOAD] SFTP connection failed – aborting.")
        return

    if dry_run:
        logger.info("[UPLOAD] Dry-run enabled – no files will be transferred")

    newly_uploaded: Dict[str, List[str]] = {}
    # Preserve the initial remote working directory so that subsequent path
    # computations remain stable even if the SFTP client's CWD is altered by
    # other helper functions.
    initial_cwd = sftp_client.getcwd() or "/"

    try:
        # ------------------------------------------------------------------#
        # 3a. Iterate through every leaf directory                           #
        # ------------------------------------------------------------------#
        for path_tuple, local_files in local_map.items():
            # Detect when *path_tuple* is a file name. In that case, upload it
            # relative to the dataset root instead of treating it as a
            # sub-directory.
            is_direct_file = os.path.isfile(os.path.join(dataset_root, *path_tuple))

            if path_tuple:
                if is_direct_file:
                    # Summary key should be the file name itself.
                    top_folder = path_tuple[-1]
                elif (
                    path_tuple[: len(deriv_parts)] == tuple(deriv_parts)
                    and len(path_tuple) > len(deriv_parts)
                ):
                    # Skip the configured derivatives prefix to mimic non-derivative behaviour.
                    top_folder = path_tuple[len(deriv_parts)]
                else:
                    top_folder = path_tuple[0]
            else:
                # For pattern-only leaf steps (e.g. "*.fsf") the process still
                # records the filename as the top-level "folder" in the summary
                # later.
                top_folder = None

            # ------------------------------------------------------------------
            # Work out where the files actually live on disk for this entry.
            #
            # Cases:
            #   * Direct single file at dataset root:
            #       path_tuple = ("dataset_description.json",)
            #       is_direct_file = True
            #       → local_subpath = dataset_root
            #
            #   * Direct file in a deep directory:
            #       path_tuple = ("derivatives","fsl","feat","fsf","file.fsf")
            #       is_direct_file = True
            #       → local_subpath = dataset_root / "derivatives/fsl/feat/fsf"
            #
            #   * Directory-style uploads:
            #       path_tuple = ("sub-002","ses-01","func")
            #       is_direct_file = False
            #       → local_subpath = dataset_root / "sub-002/ses-01/func"
            #
            #   * Pattern-only leaf steps (e.g. "derivatives fsl feat fsf '*.fsf'"):
            #       path_tuple = ()
            #       local_files = ["file1.fsf", "file2.fsf", ...]
            #       → local_subpath = dataset_root / "derivatives/fsl/feat/fsf"
            # ------------------------------------------------------------------
            if is_direct_file:
                if path_tuple and len(path_tuple) > 1:
                    # Drop the final component (the filename) to get the
                    # directory where the file actually resides.
                    local_subpath = os.path.join(dataset_root, *path_tuple[:-1])
                else:
                    # Single-file upload at the dataset root.
                    local_subpath = dataset_root
            else:
                local_subpath = (
                    os.path.join(dataset_root, *path_tuple) if path_tuple else dataset_root
                )

            # Special case: when local_map has an *empty* path_tuple but the
            # last CLI step is a glob (e.g. "derivatives fsl feat fsf '*.fsf'"),
            # the files physically live under dataset_root / steps[:-1], even
            # though they are logically treated as flat userfiles on the
            # provider.
            if (not path_tuple) and steps and _looks_like_glob(steps[-1]):
                local_subpath = os.path.join(dataset_root, *steps[:-1]) or dataset_root

            logger.info("[UPLOAD] Scanning local path: %s", local_subpath)

            remote_path_tuple = remap_path_tuple(path_tuple, path_map)

            # Preserve the initial SFTP working directory (or user-provided
            # remote root) so that path computations remain stable even if
            # ``ensure_remote_dir_structure`` changes the current directory
            # as a side effect.
            sftp_base = remote_root or initial_cwd

            if not is_direct_file and path_tuple:
                parent_remote = (
                    os.path.dirname(
                        build_remote_path(
                            remote_path_tuple,
                            is_direct_file,
                            sftp_base,
                            cfg=pipeline_cfg,
                        )
                    )
                    or "/"
                )
                logger.info(
                    "[UPLOAD] Uploading %s → %s", path_tuple[-1], parent_remote
                )

            # Build absolute remote path using the preserved base directory
            # instead of the mutable SFTP CWD.
            remote_full_path = build_remote_path(
                remote_path_tuple,
                is_direct_file,
                sftp_base,
                cfg=pipeline_cfg,
            )

            # Decide how this subtree will appear on CBRAIN so that path
            # normalisation can choose the appropriate "root" purely from
            # the upload context.
            if rewrite_absolute_paths:
                norm_root_rel, norm_flatten = _compute_normalization_root(
                    path_tuple,
                    is_direct_file,
                    deriv_parts,
                )
            else:
                norm_root_rel, norm_flatten = None, False

            # Ensure the remote directory structure mirrors the local path.
            if not dry_run:
                if ensure_remote_dir_structure(
                    sftp_client,
                    remote_path_tuple,
                    pipeline_cfg,
                    base_dir=sftp_base,
                ):
                    logger.debug(
                        "[UPLOAD] Created remote directories: %s", remote_full_path
                    )
            else:
                logger.debug(
                    "[DRY] Would ensure remote directories: %s", remote_full_path
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
                # Local source path (original dataset)
                source_path = Path(local_subpath) / fname

                # Optionally create a normalized copy with rewritten internal paths.
                upload_path = source_path
                if rewrite_absolute_paths:
                    upload_path = normalize_file_for_upload(
                        upload_path,
                        dataset_root_path,
                        temp_root,
                        pipeline_cfg,
                        dry_run=dry_run,
                        root_rel=norm_root_rel,
                        flatten=norm_flatten,
                    )

                if is_direct_file:
                    rpath = f"{remote_full_path.rstrip('/')}/{fname}"
                else:
                    rpath = f"{remote_full_path.rstrip('/')}/{fname}"

                if dry_run:
                    logger.info("[DRY] Would upload %s → %s", fname, rpath)
                else:
                    logger.info("[UPLOAD] Uploading %s → %s", fname, rpath)
                    try:
                        sftp_client.put(str(upload_path), rpath)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("[UPLOAD] Failed to upload %s: %s", fname, exc)
                        continue

            if top_folder:
                # Preserve sub-directory context for single-file uploads so
                # registration receives the full relative path (e.g.
                # ``derivatives/license.txt`` instead of just ``license.txt``).
                if is_direct_file and path_tuple and len(path_tuple) > 1:
                    relative_missing = ["/".join((*path_tuple[:-1], f)) for f in missing_on_remote]
                else:
                    relative_missing = list(missing_on_remote)

                if is_direct_file or not path_tuple:
                    # For single-file or pattern-only uploads, record just the
                    # filename as the "relative path". This makes the summary
                    # look like:
                    #   "file.fsf": ["file.fsf"]
                    newly_uploaded.setdefault(top_folder, []).extend(relative_missing)
                else:
                    # Directory-style uploads (e.g. sub-*/ses-*/anat):
                    # keep listing the missing filenames under the top folder.
                    newly_uploaded.setdefault(top_folder, []).extend(relative_missing)

    finally:
        # Always close the SFTP session to free network resources.
        sftp_client.close()
        ssh_client.close()
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)

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

        if newly_uploaded:
            basenames: List[str] = []
            for key, items in newly_uploaded.items():
                file_paths = [i for i in items if "/" in i]
                if file_paths:
                    basenames.extend(file_paths)
                else:
                    basenames.append(key)
        else:
            basenames = list(all_targets)
        if filetypes is None:
            cb_types = [guess_filetype(b, cfg) for b in basenames]
        else:
            filetypes = filetypes or ["BidsSubject"]
            cb_types = [
                (filetypes[0] if len(filetypes) == 1 else filetypes[i])
                for i in range(len(basenames))
            ]

        if dry_run:
            logger.info(
                "[DRY] Would register %d new userfiles on provider %d",
                len(basenames),
                dp_id,
            )
        else:
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

                if dry_run:
                    logger.info(
                        "[DRY] Would move userfile %d (%s) → provider %d",
                        uf_id,
                        folder,
                        move_provider,
                    )
                else:
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
    cfg: Mapping[str, object] | None = None,
    base_dir: str | None = None,
) -> bool:
    """Create directories on the SFTP server as needed.

    The function ignores the final component when it refers to an existing
    local file, enabling commands such as ``cbrain-cli --upload-bids-and-sftp-files
    dataset_description.json`` to place the JSON at ``/dataset_description.json``
    instead of creating a directory of that name.

    Args:
        sftp_client: Active :class:`paramiko.SFTPClient` instance.
        path_tuple: Positional components relative to the SFTP root (e.g.
            ``('sub-001', 'ses-01', 'anat')``).
        cfg: Optional configuration dictionary providing the derivatives root.
        base_dir: Base directory for building the remote path. Defaults to the
            current directory of the SFTP client.

    Returns:
        bool: ``True`` if any directory was created; otherwise ``False``.
    """
    import os

    created_any = False
    current_path = "/"
    sftp_client.chdir("/")

    # Determine whether the final component is a file to replicate the
    # behaviour of :func:`build_remote_path` when computing the target
    # directory.
    is_file = False
    if path_tuple:
        last_part = path_tuple[-1]
        if "." in last_part:
            local_probe = os.path.join(os.getcwd(), *path_tuple)
            if os.path.isfile(local_probe):
                is_file = True

    # Compute the remote directory path according to the same rules used when
    # uploading files.  This avoids creating unnecessary directories such as a
    # leading derivatives folder for single file uploads.
    remote_dir = build_remote_path(
        path_tuple, is_file, base_dir or sftp_client.getcwd() or "/", cfg=cfg
    )

    # Nothing to create when targeting the SFTP root.
    components = [p for p in remote_dir.strip("/").split("/") if p]

    for part in components:
        next_path = os.path.join(current_path, part).replace("\\", "/")
        try:
            sftp_client.stat(next_path)
            sftp_client.chdir(next_path)
            current_path = next_path
            continue
        except FileNotFoundError:
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


def _looks_like_glob(component: str) -> bool:
    """Return True if a step contains common glob metacharacters."""
    return any(ch in component for ch in "*?[")


def _compute_normalization_root(
    path_tuple: Tuple[str, ...],
    is_direct_file: bool,
    deriv_parts: Sequence[str],
) -> tuple[Path | None, bool]:
    """
    Decide how embedded paths should be rewritten, purely from how this
    subtree is uploaded to CBRAIN.

    Returns (root_rel, flatten) where:

      * root_rel: Path relative to the BIDS dataset root that represents
                  the logical "root" of this userfile on CBRAIN.
                  Examples:
                    - Path("sub-002")   for subject-level trees
                    - Path(".")        for dataset/derivatives trees
                    - None             when flatten is True

      * flatten:  When True, embedded paths are reduced to basenames
                  (flat uploads, e.g. standalone .fsf files at the
                  provider root).
    """
    # 1. Explicit single-file uploads: always flatten.
    if is_direct_file:
        return None, True

    # 2. Root-level file matches (e.g. design.fsfs found at dataset root
    #    via a pattern like "derivatives fsl feat fsf *.fsf") behave like
    #    flat uploads on CBRAIN as well.
    if not path_tuple:
        return None, True

    # 3. Under the configured derivatives root: treat dataset root as
    #    the logical root for path rewriting.
    if deriv_parts and path_tuple[: len(deriv_parts)] == tuple(deriv_parts):
        return Path("."), False

    # 4. Generic subject-style trees: userfile root is the first directory
    #    component (keeps things BIDS-friendly without hard-coding "sub-").
    first = path_tuple[0]
    if first:
        return Path(first), False

    # 5. Fallback: dataset-root semantics for any other tree.
    return Path("."), False
