"""
High-level helpers for downloading CBRAIN-generated derivative folders.

This module centralises *all* path-resolution logic and metadata handling
required by the :pymod:`bids_cbrain_runner.commands.download` CLI.  Only
low-level network I/O for SFTP transfers is delegated elsewhere; the code
here focuses on **where** files should be placed and **how** to keep those
files BIDS-compliant once they arrive on disk.

Key responsibilities
--------------------
1. **Destination discovery** – :func:`resolve_output_dir` chooses an output
   location by merging package defaults with any overrides found in
   ``code/config/config.yaml``.
2. **Metadata generation** – :func:`maybe_write_dataset_description`
   ensures that a minimal *dataset_description.json* exists, following
   BIDS-derivatives recommendations.
3. **Download strategies** – two public helpers implement alternative copy
   behaviours:
   • :func:`naive_download`  – plain recursive mirror
   • :func:`flattened_download`  – remove an additional wrapper directory
4. **Recursive walker** – :func:`_naive_recursive` is shared by both public
   strategies and performs the depth-first copy while honouring *skip-dirs*
   and *force* semantics.

All functions are **side-effect free** unless explicitly documented
(otherwise they read from disk/network but do not modify global state).  No
function mutates its input arguments.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence, Set

import yaml  # noqa: F401 – retained for potential future YAML writes

from bids_cbrain_runner.commands.sftp import list_subdirs_and_files

from .metadata import runner_generatedby_entry

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Destination helpers & metadata writers
# ────────────────────────────────────────────────────────────────────────────
def resolve_output_dir(
    bids_root: str | Path,
    tool_name: str,
    config_dict: Mapping[str, object] | None,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Return (and optionally create) the derivatives directory for *tool_name*.

    The lookup order matches the philosophy used throughout
    *bids_cbrain_runner*—**explicit overrides first, sensible defaults
    last**:

    1. When *config_dict* contains a value for
       ``cbrain.<tool_name>.<tool_name>_output_dir``, use it verbatim if
       absolute, or relative to *bids_root* otherwise.
    2. Fallback to ``<bids_root>/derivatives/<tool_name>`` if no override is
       present.

    Args:
        bids_root: Absolute path to the BIDS dataset root (the folder that
            contains *dataset_description.json*).
        tool_name: Short slug identifying the CBRAIN tool.
        config_dict: Deep-merged configuration returned by
            :func:`bids_cbrain_runner.api.config_loaders.load_pipeline_config`.
            The argument may be *None* when no configuration is available.
        force: When *True*, ensure that the directory hierarchy exists even
            if it had to be created just now.  Has no effect when the path
            is already present.
        dry_run: When *True*, skip directory creation and merely return the
            resolved path.

    Returns:
        Absolute path to the directory in which derivatives should be
        downloaded.

    Notes:
        The function never raises on missing config keys; it silently falls
        back to the default location.  Any *unexpected* exception while
        parsing *config_dict* is logged but does not abort execution.
    """
    # Default location beneath <BIDS_ROOT>/derivatives
    out_dir = os.path.join(bids_root, "derivatives", tool_name)

    # Attempt to honour an explicit override from the YAML configuration
    try:
        if config_dict:
            tool_conf = config_dict.get("cbrain", {}).get(tool_name, {})
            candidate = tool_conf.get(f"{tool_name}_output_dir")
            if candidate:
                out_dir = (
                    candidate if os.path.isabs(candidate) else os.path.join(bids_root, candidate)
                )
    except Exception as exc:  # noqa: BLE001 – diagnostic only
        logger.warning("Could not parse config for %s output directory: %s", tool_name, exc)

    # Create the directory tree when needed
    if not dry_run and (force or not os.path.exists(out_dir)):
        Path(out_dir).mkdir(parents=True, exist_ok=True)

    return out_dir


def maybe_write_dataset_description(
    out_dir: str | Path,
    tool_name: str,
    config_dict: Mapping[str, object] | None,
    *,
    dry_run: bool = False,
) -> None:
    """Create a minimal *dataset_description.json* in *out_dir* when missing.

    The JSON metadata are compiled from the
    ``dataset_descriptions.cbrain.<tool_name>`` entry in *config_dict*.
    Fields absent from the YAML are simply omitted to avoid inventing
    potentially misleading metadata.

    Args:
        out_dir: Destination directory that should contain
            *dataset_description.json*.
        tool_name: Tool identifier used to look up metadata in *config_dict*.
        config_dict: Combined defaults + project-specific overrides.  The
            function is a no-op when *None* is provided.
        dry_run: When *True*, log the JSON that **would** be written but
            skip file creation.

    Side Effects:
        Writes *dataset_description.json* to *out_dir* unless *dry_run* is
        *True* or the file already exists.
    """
    dd_path = os.path.join(out_dir, "dataset_description.json")

    # Fast exit when nothing needs to be done
    if os.path.exists(dd_path) or not config_dict:
        return

    try:
        tool_meta: Mapping[str, object] = config_dict["dataset_descriptions"]["cbrain"][tool_name]  # type: ignore[index]
    except KeyError:
        # No metadata available for this tool – silently ignore
        return

    generated_by = [
        runner_generatedby_entry(),
        *[
            {
                "Name": g.get("name", ""),
                "Version": g.get("version", ""),
                "CodeURL": g.get("codeURL", ""),
                "Description": g.get("description", ""),
            }
            for g in tool_meta.get("generatedby", [])
        ],
    ]

    dataset_json: MutableMapping[str, object] = {
        "Name": tool_meta.get("name", tool_name),
        "BIDSVersion": tool_meta.get("bids_version", ""),
        "DatasetType": tool_meta.get("dataset_type", "derivative"),
        "PipelineDescription": {
            "Name": tool_meta.get("name", tool_name),
            "Version": tool_meta.get("version", ""),
            "Description": tool_meta.get("description", ""),
        },
        "GeneratedBy": generated_by,
    }

    if dry_run:
        logger.info("[DRY RUN] Would write dataset_description.json to %s", dd_path)
        logger.debug(json.dumps(dataset_json, indent=2))
        return

    try:
        with open(dd_path, "w", encoding="utf-8") as fh:
            json.dump(dataset_json, fh, indent=2)
        logger.info("Created dataset_description.json → %s", dd_path)
    except Exception as exc:  # noqa: BLE001 – disk I/O failure
        logger.error("Failed to write dataset_description.json: %s", exc)


# ────────────────────────────────────────────────────────────────────────────
# Download strategies (public API)
# ────────────────────────────────────────────────────────────────────────────
def flattened_download(
    sftp,
    remote_dir: str,
    local_root: str | Path,
    tool_name: str,
    *,
    skip_dirs: Sequence[str] | None = None,
    keep_dirs: Sequence[str] | None = None,
    wrapper: str | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Download *remote_dir* while removing an extra wrapper directory.

    Many CBRAIN pipelines place results inside a top-level folder equal to
    the tool name.  Flattening removes this folder so that the output fits
    neatly under the subject/session hierarchy required by downstream BIDS
    derivatives.

    The function supports two optional lists:

    * *skip_dirs* – names that are **never** downloaded
    * *keep_dirs* – additional top-level directories to download
      *unflattened* (e.g. ``logs`` or ``work``)

    Args:
        sftp: An **active** Paramiko SFTP client.
        remote_dir: Absolute remote directory to copy.
        local_root: Local root directory for the download target.
        tool_name: CBRAIN tool slug; used as the default *wrapper*.
        skip_dirs: Sub-directories to ignore entirely.
        keep_dirs: Sub-directories that bypass the flattening logic.
        wrapper: Explicit name of the wrapper directory.  Defaults to
            *tool_name* when *None*.
        dry_run: If *True*, log planned transfers but skip network/disk I/O.
        force: If *True*, overwrite existing local files.

    Raises:
        Any exception from Paramiko I/O propagates to the caller; handling is
        the responsibility of the CLI layer.
    """
    skip_dirs_set: Set[str] = set(skip_dirs or [])
    keep_dirs_set: Set[str] = set(keep_dirs or [])
    wrapper = wrapper or tool_name

    # Remove any keep-dirs that are explicitly skipped and abort when the
    # wrapper itself is marked for exclusion
    keep_dirs_set -= skip_dirs_set
    if wrapper in skip_dirs_set:
        return

    # ------------------------------------------------------------------ #
    # Derive sub- and ses- identifiers from the remote path              #
    # ------------------------------------------------------------------ #
    name = os.path.basename(remote_dir.lstrip("/"))
    parts: list[str] = name.split("_")
    sub = next((p for p in parts if p.startswith("sub-")), None)
    ses = next((p for p in parts if p.startswith("ses-")), None)
    if not sub:
        logger.warning("Could not infer *sub-* directory from %s", remote_dir)

    primary = (
        os.path.join(local_root, sub, ses)
        if sub and ses
        else os.path.join(local_root, sub) if sub else os.path.join(local_root, name)
    )

    # Map top-level remote dirs → local destinations
    mapping: dict[str, str] = {wrapper: primary}
    for kd in keep_dirs_set - {wrapper}:
        mapping[kd] = (
            os.path.join(local_root, kd, sub, ses)
            if sub and ses
            else os.path.join(local_root, kd, sub or name)
        )

    for dest in mapping.values():
        if not dry_run:
            Path(dest).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Immediate listing of remote_dir to decide which dirs to traverse   #
    # ------------------------------------------------------------------ #
    subdirs, files = list_subdirs_and_files(sftp, remote_dir)
    subdirs = [d for d in subdirs if d not in skip_dirs_set]
    subdirs = [d for d in subdirs if d == wrapper or d in mapping]

    for sd in subdirs:
        orig_src = os.path.join(remote_dir, sd)
        dst = mapping[sd]

        # Keep track of any files present directly under the keep-dir root
        root_subdirs, root_files = list_subdirs_and_files(sftp, orig_src)

        # Heuristic: some tools wrap output inside a single sub-*/ses-* folder
        src = orig_src
        if sd == wrapper:
            inner = root_subdirs
            if len(inner) == 1 and inner[0].startswith("sub-"):
                src = os.path.join(src, inner[0])

        elif sd in keep_dirs_set:
            inner = root_subdirs
            # Normalise keep-dirs so they align with the subject folder
            if len(inner) == 1 and inner[0] == sub:
                src = os.path.join(src, sub)
                inner, _ = list_subdirs_and_files(sftp, src)
            if ses and len(inner) == 1 and inner[0] == ses:
                src = os.path.join(src, ses)

        _naive_recursive(
            sftp,
            src,
            dst,
            skip_dirs=skip_dirs_set,
            dry_run=dry_run,
            force=force,
        )

        # When the source path was normalised away from orig_src, ensure that
        # any loose files in the keep-dir root are also downloaded
        if sd in keep_dirs_set and src != orig_src:
            for fname in root_files:
                src_file = os.path.join(orig_src, fname)
                dst_file = os.path.join(dst, fname)
                if not force and os.path.exists(dst_file):
                    continue
                if dry_run:
                    logger.info("[DRY] Would GET %s → %s", src_file, dst_file)
                else:
                    sftp.get(src_file, dst_file)
                    logger.info("GET %s → %s", src_file, dst_file)

    # Copy any loose files located *directly* under remote_dir
    for fname in files:
        src = os.path.join(remote_dir, fname)
        dst = os.path.join(primary, fname)
        if not force and os.path.exists(dst):
            continue
        if dry_run:
            logger.info("[DRY] Would GET %s → %s", src, dst)
        else:
            sftp.get(src, dst)
            logger.info("GET %s → %s", src, dst)


def naive_download(
    sftp,
    remote_dir: str,
    local_root: str | Path,
    *,
    skip_dirs: Sequence[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Recursively mirror *remote_dir* under *local_root*.

    This strategy copies the remote hierarchy **verbatim**—no flattening
    and no special handling for tool-specific folder names.

    Args:
        sftp: Active Paramiko SFTP client.
        remote_dir: Absolute remote directory to mirror.
        local_root: Local directory that becomes the root of the mirror.
        skip_dirs: Sub-directories to skip entirely during recursion.
        dry_run: If *True*, log operations without performing them.
        force: If *True*, overwrite any existing local files.
    """
    base = os.path.basename(remote_dir.lstrip("/"))
    dest = os.path.join(local_root, base)

    _naive_recursive(
        sftp,
        remote_dir,
        dest,
        skip_dirs=set(skip_dirs or []),
        dry_run=dry_run,
        force=force,
    )


# ────────────────────────────────────────────────────────────────────────────
# Internal shared walker
# ────────────────────────────────────────────────────────────────────────────
def _naive_recursive(
    sftp,
    remote_path: str,
    local_path: str,
    *,
    skip_dirs: Set[str],
    dry_run: bool,
    force: bool,
) -> None:
    """Depth-first copy of *remote_path* → *local_path*.

    Args:
        sftp: Active Paramiko SFTP client.
        remote_path: Current remote directory.
        local_path: Corresponding local directory.
        skip_dirs: Directory names that must not be traversed.
        dry_run: If *True*, simulate transfers only.
        force: If *True*, overwrite existing local files.

    Notes:
        The function is intentionally *chatty* at INFO level to facilitate
        monitoring of long transfers.
    """
    subdirs, files = list_subdirs_and_files(sftp, remote_path)
    subdirs = [d for d in subdirs if d not in skip_dirs]

    if not dry_run:
        Path(local_path).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # File transfers at current depth                                    #
    # ------------------------------------------------------------------ #
    for fname in files:
        src = os.path.join(remote_path, fname)
        dst = os.path.join(local_path, fname)
        if not force and os.path.exists(dst):
            continue
        if dry_run:
            logger.info("[DRY] Would GET %s → %s", src, dst)
        else:
            sftp.get(src, dst)
            logger.info("GET %s → %s", src, dst)

    # ------------------------------------------------------------------ #
    # Recurse into sub-directories                                        #
    # ------------------------------------------------------------------ #
    for sd in subdirs:
        _naive_recursive(
            sftp,
            os.path.join(remote_path, sd),
            os.path.join(local_path, sd),
            skip_dirs=skip_dirs,
            dry_run=dry_run,
            force=force,
        )
