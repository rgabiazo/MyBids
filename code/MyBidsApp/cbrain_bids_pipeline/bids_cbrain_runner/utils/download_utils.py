"""High-level helpers for downloading CBRAIN-generated derivative folders.

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
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Mapping, MutableMapping, Sequence, Set

import yaml  # noqa: F401 – retained for potential future YAML writes

from bids_cbrain_runner.commands.sftp import list_subdirs_and_files

from .metadata import runner_generatedby_entry


def _find_session_component(path: str) -> str | None:
    """Return the ``ses-<label>`` component from *path* if present."""
    for part in Path(path).parts:
        if part.startswith("ses-"):
            return part
    return None


def _find_subject_component(path: str) -> str | None:
    """Return the ``sub-<label>`` component from *path* if present."""
    for part in Path(path).parts:
        if part.startswith("sub-"):
            return part
    return None


def _normalize_session_name(directory: str, fname: str) -> str:
    """Insert or replace the session label in *fname* based on *directory*.

    The function inspects *directory* for a ``ses-`` component and ensures
    that *fname* contains the same session label.  When a different session is
    already present in the file name it is replaced.  If the file lacks any
    session token the label is inserted after the subject identifier when
    available or prepended otherwise.
    """
    ses = _find_session_component(directory)
    if not ses:
        return fname

    import re

    if re.search(r"ses-[^_]+", fname):
        return re.sub(r"ses-[^_]+", ses, fname)

    m = re.match(r"(sub-[^_]+)(.*)", fname)
    if m:
        return f"{m.group(1)}_{ses}{m.group(2)}"
    return f"{ses}_{fname}"


def _normalize_subject_name(directory: str, fname: str) -> str:
    """Insert or replace the subject label in *fname* based on *directory*."""
    sub = _find_subject_component(directory)
    if not sub:
        return fname

    import re

    if re.search(r"sub-[^_]+", fname):
        return re.sub(r"sub-[^_]+", sub, fname)

    return f"{sub}_{fname}"


def _path_matches(rel_path: str, patterns: Sequence[str]) -> bool:
    """Return *True* if *rel_path* shares a prefix with any glob in *patterns*.

    The check considers both ancestor and descendant relationships using
    component-wise glob matching.  An empty *patterns* sequence always
    evaluates to *False*; callers should short-circuit accordingly when no
    filtering is desired.
    """

    rel_parts = PurePosixPath(rel_path).parts
    for pat in patterns:
        pat_parts = PurePosixPath(pat).parts
        min_len = min(len(rel_parts), len(pat_parts))
        if all(fnmatch(rel_parts[i], pat_parts[i]) for i in range(min_len)):
            return True
    return False


def should_include(rel_path: str, patterns: Sequence[str] | None) -> bool:
    """Decide whether *rel_path* should be processed given *patterns*.

    When *patterns* is empty or *None* the function always returns *True*.
    Otherwise the relative path is allowed only if it matches or is a prefix of
    any provided glob pattern.
    """

    if not patterns:
        return True
    if rel_path in ("", "."):
        return True
    return _path_matches(rel_path, patterns)


def _transfer_file(
    sftp,
    src_file: str,
    dst_dir: str,
    fname: str,
    *,
    normalize_session: bool,
    normalize_subject: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Copy *src_file* into *dst_dir* honouring force/dry-run semantics."""
    out_name = fname
    if normalize_subject:
        out_name = _normalize_subject_name(dst_dir, out_name)
    if normalize_session:
        out_name = _normalize_session_name(dst_dir, out_name)
    dst_file = os.path.join(dst_dir, out_name)
    if not force and os.path.exists(dst_file):
        return
    if dry_run:
        logger.info("[DRY] Would GET %s → %s", src_file, dst_file)
    else:
        sftp.get(src_file, dst_file)
        logger.info("GET %s → %s", src_file, dst_file)

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# Destination helpers & metadata writers
# ────────────────────────────────────────────────────────────────────────────
def resolve_output_dir(
    bids_root: str | Path,
    tool_name: str,
    config_dict: Mapping[str, object] | None,
    *,
    output_dir_name: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Return the derivatives directory for ``tool_name`` (create if missing).

    The lookup order matches the philosophy used throughout
    *bids_cbrain_runner*—explicit overrides first, sensible defaults
    last:

    1. When *config_dict* contains a value for
       ``cbrain.<tool_name>.<tool_name>_output_dir``, use it verbatim if
       absolute, or relative to *bids_root* otherwise.
    2. Fallback to ``<bids_root>/derivatives/<output_dir_name>`` if no override
       is present (or ``tool_name`` when *output_dir_name* is *None*).

    Args:
        bids_root: Absolute path to the BIDS dataset root (the folder that
            contains *dataset_description.json*).
        tool_name: Short slug identifying the CBRAIN tool.
        config_dict: Deep-merged configuration returned by
            :func:`bids_cbrain_runner.api.config_loaders.load_pipeline_config`.
            The argument may be *None* when no configuration is available.
        output_dir_name: Override for the final directory name when the
            configuration does not specify one explicitly.
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
        parsing *config_dict* is logged but does not abort execution.  When
        *output_dir_name* is provided it **always** takes precedence over
        configuration-derived locations.
    """
    # Start with the default <BIDS_ROOT>/derivatives/<tool_name>
    out_dir = os.path.join(bids_root, "derivatives", tool_name)

    # Honour an explicit override from the YAML configuration
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

    # Finally, allow a CLI-supplied output directory to override everything
    if output_dir_name:
        out_dir = (
            output_dir_name
            if os.path.isabs(output_dir_name)
            else os.path.join(bids_root, "derivatives", output_dir_name)
        )

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
    skip_files: Sequence[str] | None = None,
    subject_dirs: Sequence[str] | None = None,
    wrapper: str | None = None,
    path_map: Mapping[str, Sequence[str]] | None = None,
    include_dirs: Sequence[str] | None = None,
    normalize_session: bool = False,
    normalize_subject: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Download *remote_dir* while removing an extra wrapper directory.

    Many CBRAIN pipelines place results inside a top-level folder equal to
    the tool name.  Flattening removes this folder so that the output fits
    neatly under the subject/session hierarchy required by downstream BIDS
    derivatives.

    The function supports three optional lists:

    * *skip_dirs* – names that are **never** downloaded
    * *keep_dirs* – additional top-level directories to download
      *unflattened* (e.g. ``logs`` or ``work``)
    * *subject_dirs* – keep-dirs whose contents should be placed under
      the inferred ``sub-``/``ses-`` hierarchy
    * *skip_files* – filenames to ignore entirely (e.g. ``dataset_description.json``)
    * *path_map* – remap specific directory names to alternate destination
      paths.  When multiple destinations are given the directory is downloaded
      once and additional locations are created as relative symlinks.
    * *normalize_session* – ensure filenames reflect the session directory
      they reside in
    * *normalize_subject* – ensure filenames include the subject directory
      they reside in

    Args:
        sftp: An **active** Paramiko SFTP client.
        remote_dir: Absolute remote directory to copy.
        local_root: Local root directory for the download target.
        tool_name: CBRAIN tool slug; used as the default *wrapper*.
        skip_dirs: Sub-directories to ignore entirely.
        keep_dirs: Sub-directories that bypass the flattening logic.
        skip_files: Filenames to skip during transfer.
        wrapper: Explicit name of the wrapper directory.  Defaults to
            *tool_name* when *None*.
        path_map: Mapping of directory names to alternative destination paths
            relative to their parent.
        include_dirs: Glob patterns restricting the download to specific
            remote paths.
        normalize_session: If *True*, ensure filenames include the session
            label of their containing directory.
        normalize_subject: If *True*, ensure filenames include the subject
            label of their containing directory.
        dry_run: If *True*, log planned transfers but skip network/disk I/O.
        force: If *True*, overwrite existing local files.

    Raises:
        Any exception from Paramiko I/O propagates to the caller; handling is
        the responsibility of the CLI layer.
    """
    skip_dirs_set: Set[str] = set(skip_dirs or [])
    keep_dirs_set: Set[str] = set(keep_dirs or [])
    skip_files_set: Set[str] = set(skip_files or [])
    subject_dirs_set: Set[str] = set(subject_dirs or [])
    path_map = {k: list(v) if isinstance(v, (list, tuple)) else [v] for k, v in (path_map or {}).items()}
    wrapper = wrapper or tool_name

    # Remove any keep-dirs that are explicitly skipped and abort when the
    # wrapper itself is marked for exclusion
    keep_dirs_set -= skip_dirs_set
    if wrapper and wrapper in skip_dirs_set:
        return

    # Immediate listing of remote_dir
    subdirs, files = list_subdirs_and_files(sftp, remote_dir)
    subdirs = [d for d in subdirs if d not in skip_dirs_set]
    subdirs = [d for d in subdirs if should_include(d, include_dirs)]
    files = [f for f in files if should_include(f, include_dirs)]

    # ------------------------------------------------------------------ #
    # Derive sub- and ses- identifiers                                  #
    # ------------------------------------------------------------------ #
    import re

    name = os.path.basename(remote_dir.lstrip("/"))
    sub_match = re.search(r"(sub-[^_/\-]+)", name)
    ses_match = re.search(r"(ses-[^_/\-]+)", name)
    sub = sub_match.group(1) if sub_match else None
    ses = ses_match.group(1) if ses_match else None

    if not sub:
        candidate = next((d for d in subdirs if d.startswith("sub-")), None)
        if candidate:
            sub = candidate
            inner, _ = list_subdirs_and_files(sftp, os.path.join(remote_dir, candidate))
            ses = next((d for d in inner if d.startswith("ses-")), ses)

    if not sub:
        logger.warning("Could not infer *sub-* directory from %s", remote_dir)

    primary = (
        os.path.join(local_root, sub, ses)
        if sub and ses
        else os.path.join(local_root, sub) if sub else local_root
    )

    mapping: dict[str, str] = {}
    wrapper_present = wrapper in subdirs if wrapper else False

    if wrapper_present:
        mapping[wrapper] = primary
        for kd in keep_dirs_set - {wrapper}:
            if not should_include(kd, include_dirs):
                continue
            mapping[kd] = (
                os.path.join(local_root, kd, sub, ses)
                if sub and ses
                else os.path.join(local_root, kd, sub) if sub else os.path.join(local_root, kd)
            )
    else:
        for sd in [d for d in subdirs if d.startswith("sub-")]:
            mapping[sd] = os.path.join(local_root, sd)
        for kd in keep_dirs_set:
            if not should_include(kd, include_dirs):
                continue
            base = os.path.join(local_root, kd)
            if kd in subject_dirs_set and sub:
                mapping[kd] = (
                    os.path.join(base, sub, ses)
                    if ses
                    else os.path.join(base, sub)
                )
            else:
                mapping[kd] = base

    for dest in mapping.values():
        if not dry_run:
            Path(dest).mkdir(parents=True, exist_ok=True)

    subdirs = [d for d in subdirs if d in mapping]

    for sd in subdirs:
        orig_src = os.path.join(remote_dir, sd)
        dst = mapping[sd]

        root_subdirs, root_files = list_subdirs_and_files(sftp, orig_src)
        src = orig_src

        if wrapper_present and sd == wrapper:
            inner = root_subdirs
            if len(inner) == 1 and inner[0].startswith("sub-"):
                src = os.path.join(src, inner[0])
        elif wrapper_present and sd in keep_dirs_set:
            inner = root_subdirs
            if len(inner) == 1 and sub and inner[0] == sub:
                src = os.path.join(src, sub)
                inner, _ = list_subdirs_and_files(sftp, src)
            if ses and len(inner) == 1 and inner[0] == ses:
                src = os.path.join(src, ses)
        elif not wrapper_present and sd in subject_dirs_set:
            if sub and sub in root_subdirs:
                # Copy root files to destination first.  Special-case
                # ``dataset_description.json`` so that it always lands at the
                # root of the keep-dir rather than beneath the subject
                # hierarchy (e.g. ``QC/dataset_description.json`` instead of
                # ``QC/sub-001/dataset_description.json``).
                base_dest = os.path.join(local_root, sd)
                if not dry_run:
                    Path(base_dest).mkdir(parents=True, exist_ok=True)
                for fname in root_files:
                    if fname in skip_files_set:
                        continue
                    rel_file = os.path.join(sd, fname)
                    if not should_include(rel_file, include_dirs):
                        continue
                    src_file = os.path.join(orig_src, fname)
                    dest_dir = base_dest if fname == "dataset_description.json" else dst
                    _transfer_file(
                        sftp,
                        src_file,
                        dest_dir,
                        fname,
                        normalize_session=normalize_session,
                        normalize_subject=normalize_subject,
                        force=force,
                        dry_run=dry_run,
                    )
                # Merge subject directory directly under destination
                _naive_recursive(
                    sftp,
                    os.path.join(orig_src, sub),
                    dst,
                    skip_dirs=skip_dirs_set,
                    skip_files=skip_files_set,
                    dry_run=dry_run,
                    force=force,
                    path_map=path_map,
                    normalize_session=normalize_session,
                    normalize_subject=normalize_subject,
                    include_dirs=include_dirs,
                    root_path=remote_dir,
                )
                root_subdirs = [d for d in root_subdirs if d != sub]
                for inner in root_subdirs:
                    _naive_recursive(
                        sftp,
                        os.path.join(orig_src, inner),
                        os.path.join(dst, inner),
                        skip_dirs=skip_dirs_set,
                        skip_files=skip_files_set,
                        dry_run=dry_run,
                        force=force,
                        path_map=path_map,
                        normalize_session=normalize_session,
                        normalize_subject=normalize_subject,
                        include_dirs=include_dirs,
                        root_path=remote_dir,
                    )
                continue
        
        _naive_recursive(
            sftp,
            src,
            dst,
            skip_dirs=skip_dirs_set,
            skip_files=skip_files_set,
            dry_run=dry_run,
            force=force,
            path_map=path_map,
            normalize_session=normalize_session,
            normalize_subject=normalize_subject,
            include_dirs=include_dirs,
            root_path=remote_dir,
        )

        if sd in keep_dirs_set and src != orig_src:
            for fname in root_files:
                if fname in skip_files_set:
                    continue
                rel_file = os.path.join(sd, fname)
                if not should_include(rel_file, include_dirs):
                    continue
                src_file = os.path.join(orig_src, fname)
                _transfer_file(
                    sftp,
                    src_file,
                    dst,
                    fname,
                    normalize_session=normalize_session,
                    normalize_subject=normalize_subject,
                    force=force,
                    dry_run=dry_run,
                )

    for fname in files:
        if fname in skip_files_set:
            continue
        if not should_include(fname, include_dirs):
            continue
        src = os.path.join(remote_dir, fname)
        _transfer_file(
            sftp,
            src,
            local_root,
            fname,
            normalize_session=normalize_session,
            normalize_subject=normalize_subject,
            force=force,
            dry_run=dry_run,
        )


def naive_download(
    sftp,
    remote_dir: str,
    local_root: str | Path,
    *,
    skip_dirs: Sequence[str] | None = None,
    skip_files: Sequence[str] | None = None,
    include_dirs: Sequence[str] | None = None,
    path_map: Mapping[str, Sequence[str]] | None = None,
    normalize_session: bool = False,
    normalize_subject: bool = False,
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
        skip_files: File names to ignore during recursion.
        include_dirs: Glob patterns restricting which paths are downloaded.
        path_map: Optional mapping of directory names to alternative
            destination paths relative to their parent.  When a directory is
            mapped to multiple locations, extra locations are created as
            relative symlinks.
        normalize_session: If *True*, ensure filenames include their session
            label when beneath a ``ses-`` directory.
        normalize_subject: If *True*, ensure filenames include their subject
            label when beneath a ``sub-`` directory.
        dry_run: If *True*, log operations without performing them.
        force: If *True*, overwrite any existing local files.
    """
    base = os.path.basename(remote_dir.lstrip("/"))
    dest = os.path.join(local_root, base)

    mapping = {k: list(v) if isinstance(v, (list, tuple)) else [v] for k, v in (path_map or {}).items()}
    _naive_recursive(
        sftp,
        remote_dir,
        dest,
        skip_dirs=set(skip_dirs or []),
        skip_files=set(skip_files or []),
        include_dirs=include_dirs,
        dry_run=dry_run,
        force=force,
        path_map=mapping,
        normalize_session=normalize_session,
        normalize_subject=normalize_subject,
        root_path=remote_dir,
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
    skip_files: Set[str],
    dry_run: bool,
    force: bool,
    path_map: Mapping[str, Sequence[str]] | None = None,
    normalize_session: bool = False,
    normalize_subject: bool = False,
    include_dirs: Sequence[str] | None = None,
    root_path: str | None = None,
    _mapped: Set[str] | None = None,
) -> None:
    """Depth-first copy of *remote_path* → *local_path*.

    Args:
        sftp: Active Paramiko SFTP client.
        remote_path: Current remote directory.
        local_path: Corresponding local directory.
        skip_dirs: Directory names that must not be traversed.
        dry_run: If *True*, simulate transfers only.
        force: If *True*, overwrite existing local files.
        path_map: Remapping rules for directory names.
        normalize_session: Ensure filenames match the session directory.
        normalize_subject: Ensure filenames include the subject directory.
        include_dirs: Optional glob patterns restricting traversal to matching
            relative paths.
        root_path: Anchor for relative path computation; defaults to the first
            ``remote_path`` provided.
        _mapped: Internal set tracking which remote paths have been remapped.

    Notes:
        The function is intentionally *chatty* at INFO level to facilitate
        monitoring of long transfers.
    """
    _mapped = _mapped or set()
    root_path = root_path or remote_path
    rel_path = os.path.relpath(remote_path, root_path).replace("\\", "/")
    if not should_include(rel_path, include_dirs):
        return
    base_name = os.path.basename(remote_path)
    if path_map and base_name in path_map and remote_path not in _mapped:
        _mapped.add(remote_path)
        parent = os.path.dirname(local_path)
        targets = [os.path.join(parent, rel) for rel in path_map[base_name]]
        for dest in targets:
            _naive_recursive(
                sftp,
                remote_path,
                dest,
                skip_dirs=skip_dirs,
                skip_files=skip_files,
                dry_run=dry_run,
                force=force,
                path_map=path_map,
                normalize_session=normalize_session,
                normalize_subject=normalize_subject,
                include_dirs=include_dirs,
                root_path=root_path,
                _mapped=_mapped,
            )
        return

    subdirs, files = list_subdirs_and_files(sftp, remote_path)
    subdirs = [d for d in subdirs if d not in skip_dirs]

    if not dry_run:
        Path(local_path).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # File transfers at current depth                                    #
    # ------------------------------------------------------------------ #
    for fname in files:
        if fname in skip_files:
            continue
        file_rel = os.path.join(rel_path, fname).lstrip("./")
        if not should_include(file_rel, include_dirs):
            continue
        src = os.path.join(remote_path, fname)
        _transfer_file(
            sftp,
            src,
            local_path,
            fname,
            normalize_session=normalize_session,
            normalize_subject=normalize_subject,
            force=force,
            dry_run=dry_run,
        )

    # ------------------------------------------------------------------ #
    # Recurse into sub-directories                                        #
    # ------------------------------------------------------------------ #
    for sd in subdirs:
        sub_rel = os.path.join(rel_path, sd).lstrip("./")
        if not should_include(sub_rel, include_dirs):
            continue
        _naive_recursive(
            sftp,
            os.path.join(remote_path, sd),
            os.path.join(local_path, sd),
            skip_dirs=skip_dirs,
            skip_files=skip_files,
            dry_run=dry_run,
            force=force,
            path_map=path_map,
            normalize_session=normalize_session,
            normalize_subject=normalize_subject,
            include_dirs=include_dirs,
            root_path=root_path,
            _mapped=_mapped,
        )
