"""Convert a directory tree to a BIDS-style mapping.

Utility functions convert the structure produced by
``local_files.local_build_path_tree()`` or ``sftp.build_sftp_path_tree()``
into a JSON serialisable mapping that mirrors a typical BIDS derivative
layout.

The expected *node* structure mirrors the output of the aforementioned
helpers:

    {
        "<subdir_name>": {...},  # nested child dictionaries produced
        "_files":   [...],       # files located directly in this directory
        "_subdirs": [...]        # names of immediate sub‑directories
    }

Hidden files or directories (those whose names begin with a dot) are
ignored to stay compliant with BIDS recommendations that discourage the
use of dot‑prefixed paths in shared datasets.

The conversion rules are:
    • Sub‑directories remain nested dictionaries after conversion.
    • A *leaf* directory (i.e. one that has files but **no** sub‑
      directories) is converted to a **sorted list** of file names.
    • When a directory contains **both** sub‑directories *and* files, the
      file list is stored under the key ``"files"`` alongside converted
      sub‑directories.

Args:
    node (dict): Mapping that follows the structure shown above.

Returns:
    dict | list[str]: A BIDS-style representation of ``node``. If
    ``node`` has no sub-directories, the return value is the sorted list of
    its files. Otherwise the return value is a dictionary that may include a
    ``"files"`` key when the directory contains direct files in addition to
    sub-directories.
"""

def to_bids_style(node):
    """Recursively convert ``node`` into a BIDS-style representation.

    Args:
        node (dict): Directory mapping produced by the path-tree builders. It
            must contain the helper keys ``"_files"`` and ``"_subdirs"`` alongside
            any nested sub-directory keys.

    Returns:
        dict | list[str]: See module-level docstring for details.
    """
    # Helper lists are retrieved once to avoid repeated look-ups.
    raw_files = node.get("_files", [])
    raw_subdirs = node.get("_subdirs", [])

    # Filter out hidden entries to prevent dot‑prefixed artefacts from
    # polluting the final mapping.
    files = [f for f in raw_files if not f.startswith(".")]
    subdirs = [d for d in raw_subdirs if not d.startswith(".")]

    # Children that correspond to actual sub‑directories (i.e. keys that
    # do **not** start with an underscore).
    child_keys = [k for k in node.keys() if not k.startswith("_")]
    result = {}

    # Depth‑first conversion of each child directory ensures deterministic
    # output order by sorting child names alphabetically.
    for key in sorted(child_keys):
        subnode = node[key]
        result[key] = to_bids_style(subnode)

    # If the current directory contains **no** converted children but
    # *does* contain files, treat it as a leaf and return the sorted list
    # directly. This keeps the JSON structure concise.
    if not result and files:
        return sorted(files)

    # When both sub‑directories and files are present, store the file list
    # under a dedicated key. This mirrors how mixed‑content directories
    # are typically represented in derivative JSON outputs.
    if files:
        result["files"] = sorted(files)

    return result
