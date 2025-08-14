"""Local‑filesystem helpers that mirror the interface of the SFTP utilities.

These helpers provide a *uniform* tree‑building API for local paths so that the
same comparison logic can be applied to both local and remote (SFTP) datasets.
The design intentionally mirrors :pyfile:`bids_cbrain_runner.commands.sftp`
functions, making it trivial to swap implementations when unit‑testing or
running entirely offline.

Core responsibilities:

* Build an *in‑memory* directory tree that honours Unix‑shell wildcards (via
  :pymod:`fnmatch`).
* Support *leaf detection* when a wildcard pattern matches a *file* rather than
  a directory – critical for generic rules such as ``'*.nii.gz'``.
* Offer a convenience function that collapses the tree into
  ``{path_tuple: [filenames]}`` so that downstream download/upload code can
  iterate over *final* sub‑directories directly.

The module makes no assumptions about BIDS per se; it merely operates on
filenames and directory names.  Higher‑level code (e.g. BIDS‑aware validation)
layered on top handles semantic checks.
"""

from __future__ import annotations

import fnmatch
import logging
import os
from pathlib import Path
from typing import Dict, Iterable, List, MutableMapping, Sequence, Tuple

logger = logging.getLogger(__name__)

# Patterns ignored during directory listings (matches Finder & resource files)
DEFAULT_IGNORE_GLOBS: List[str] = ["*.DS_Store", "._*"]

# -----------------------------------------------------------------------------
# Public API – tree builders / collectors
# -----------------------------------------------------------------------------

def local_build_path_tree(
    root_dir: str | Path,
    steps: Sequence[str],
    recurse_if_no_more_steps: bool = False,
    *,
    ignore_globs: Iterable[str] = DEFAULT_IGNORE_GLOBS,
) -> Dict[str, object]:
    """Return a nested mapping that mirrors wildcard traversal under ``root_dir``.

    Example::

        >>> local_build_path_tree("/bids", ["sub-*", "ses-*", "anat"])
        {
            "sub-001": {
                "ses-01": {
                    "anat": {
                        "_files": ["sub-001_ses-01_T1w.nii.gz"]
                        "_subdirs": []
                    }
                }
            },
            "sub-002": { ... }
        }

    Args:
        root_dir: Starting directory for traversal.
        steps: Wildcard patterns applied sequentially (shell style).
        recurse_if_no_more_steps: When *True*, once *steps* is exhausted the
            walker *recursively* enumerates all remaining sub‑directories to
            discover deeper files.  Enables use‑cases such as detecting extra
            nested subject folders without explicitly listing every level in
            *steps*.
        ignore_globs: Optional patterns to ignore when listing directories.
            Defaults to :data:`DEFAULT_IGNORE_GLOBS`.

    Returns:
        Nested ``dict`` with keys representing directory names.  Two reserved
        keys are used to differentiate files vs sub‑directories:
        ``"_files"`` and ``"_subdirs"``.
    """
    path_tree: Dict[str, object] = {}
    _recursive_local_walk(
        current_dir=str(root_dir),
        steps=list(steps),
        step_index=0,
        partial_path=[],
        path_tree=path_tree,
        recurse_if_no_more_steps=recurse_if_no_more_steps,
        ignore_globs=ignore_globs,
    )
    return path_tree


# -----------------------------------------------------------------------------
# Internal recursive walker ----------------------------------------------------
# -----------------------------------------------------------------------------

def _recursive_local_walk(
    current_dir: str,
    steps: List[str],
    step_index: int,
    partial_path: List[str],
    path_tree: MutableMapping[str, object],
    recurse_if_no_more_steps: bool,
    ignore_globs: Iterable[str],
) -> None:
    """Depth‑first matcher implementing the wildcard traversal logic."""
    if step_index >= len(steps):
        # Traversal finished for the provided patterns.
        if recurse_if_no_more_steps:
            _local_walk_all_remaining(current_dir, partial_path, path_tree, ignore_globs)
        else:
            subdirs, files = local_list_subdirs_and_files(current_dir, ignore_globs)
            _insert_local_path(path_tree, partial_path, subdirs, files)
        return

    pattern = steps[step_index]
    subdirs, files = local_list_subdirs_and_files(current_dir, ignore_globs)

    # --- Match against directory names ----------------------------------------
    matched_subdirs: List[str] = [sd for sd in subdirs if fnmatch.fnmatch(sd, pattern)]
    matched_files: List[str] = [f for f in files if fnmatch.fnmatch(f, pattern)]

    # --- Handle direct file matches (leaf nodes) ------------------------------
    if matched_files:
        logger.debug("Found file(s) matching pattern '%s' in %s: %s", pattern, current_dir, matched_files)
        for fname in matched_files:
            # Treat each matching file as its own leaf path.
            _insert_local_path(path_tree, partial_path + [fname], [], [fname])
        # Do *not* recurse into sub‑directories when a file matched.
        return

    # --- Recurse into matching sub‑directories --------------------------------
    if matched_subdirs:
        for match_name in matched_subdirs:
            next_dir = os.path.join(current_dir, match_name)
            _recursive_local_walk(
                next_dir,
                steps,
                step_index + 1,
                partial_path + [match_name],
                path_tree,
                recurse_if_no_more_steps,
                ignore_globs,
            )
    else:
        # No match – optionally fall back to exhaustive recursion.
        logger.warning(
            "No local subdir/file matches pattern '%s' in %s. Continuing deeper search…",
            pattern,
            current_dir,
        )
        if recurse_if_no_more_steps:
            _local_walk_all_remaining(current_dir, partial_path, path_tree, ignore_globs)


# -----------------------------------------------------------------------------
# Helper walkers / inserters ---------------------------------------------------
# -----------------------------------------------------------------------------

def _local_walk_all_remaining(
    current_dir: str,
    partial_path: List[str],
    path_tree: MutableMapping[str, object],
    ignore_globs: Iterable[str],
) -> None:
    """Recursively add *all* remaining sub‑directories under *current_dir*."""
    subdirs, files = local_list_subdirs_and_files(current_dir, ignore_globs)
    _insert_local_path(path_tree, partial_path, subdirs, files)
    for sd in subdirs:
        _local_walk_all_remaining(
            os.path.join(current_dir, sd),
            partial_path + [sd],
            path_tree,
            ignore_globs,
        )


def local_list_subdirs_and_files(
    directory: str,
    ignore_globs: Iterable[str] = DEFAULT_IGNORE_GLOBS,
) -> Tuple[List[str], List[str]]:
    """Return ``(subdirs, files)`` found directly under *directory*.

    Args:
        directory: Path being inspected.
        ignore_globs: Patterns filtered out of the listing. Matched entries are
            skipped.

    Returns:
        A tuple ``(subdirs, files)``. Errors are logged and empty lists are
        returned when the directory cannot be read.
    """
    try:
        contents = os.listdir(directory)
        contents = [
            c for c in contents if not any(fnmatch.fnmatch(c, pat) for pat in ignore_globs)
        ]
    except FileNotFoundError:
        logger.error("[LOCAL] Directory not found: %s", directory)
        return ([], [])
    except Exception as exc:  # noqa: BLE001 – broad but intentional here
        logger.error("[LOCAL] Could not listdir '%s': %s", directory, exc)
        return ([], [])

    subdirs: List[str] = []
    files: List[str] = []
    for entry in contents:
        full_path = os.path.join(directory, entry)
        (subdirs if os.path.isdir(full_path) else files).append(entry)

    subdirs.sort()
    files.sort()
    return subdirs, files


def _insert_local_path(
    tree_dict: MutableMapping[str, object],
    path_parts: Sequence[str],
    subdirs: Sequence[str],
    files: Sequence[str],
) -> None:
    """Insert *subdirs* and *files* at the node given by *path_parts*."""
    current = tree_dict
    for part in path_parts:
        current = current.setdefault(part, {})  # type: ignore[assignment]
    current["_files"] = list(files)
    current["_subdirs"] = list(subdirs)


# -----------------------------------------------------------------------------
# Collector – collapse final tree into {path_tuple: [files]} -------------------
# -----------------------------------------------------------------------------

def local_gather_all_matched_files(path_tree: Dict[str, object]) -> Dict[Tuple[str, ...], List[str]]:
    """Return a mapping of directory tuples → list of files.

    Unlike the previous implementation which only collected files from *leaf*
    directories, this version records files for **all** directories encountered
    in ``path_tree``.  This ensures that files sitting alongside further
    sub‑directories (e.g. ``dataset_description.json`` at the root of a
    derivative) are not skipped.

    Args:
        path_tree: Nested mapping produced by :pyfunc:`local_build_path_tree`.

    Returns:
        Dictionary keyed by ``tuple`` representations of directory components.
        Example::

            {('sub-001', 'ses-01', 'anat'): ["T1w.nii.gz", ...]}
    """
    results: Dict[Tuple[str, ...], List[str]] = {}
    _recursive_collect_files(path_tree, [], results)
    return results


def _recursive_collect_files(
    node: Dict[str, object],
    path_stack: List[str],
    results: MutableMapping[Tuple[str, ...], List[str]],
) -> None:
    """Walk *node* depth-first to populate *results*."""
    subkeys: List[str] = [k for k in node.keys() if not k.startswith("_")]

    files = node.get("_files", [])  # type: ignore[arg-type]
    if files:
        results[tuple(path_stack)] = files  # type: ignore[assignment]

    for sk in subkeys:
        _recursive_collect_files(node[sk], path_stack + [sk], results)  # type: ignore[index]
