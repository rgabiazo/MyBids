"""
BIDS-root discovery utilities.

Functions here walk up the filesystem tree looking for a
*dataset_description.json* file, the canonical marker for a BIDS dataset
root.  Keeping this logic in one place avoids subtle inconsistencies when
different modules attempt discovery independently.
"""

from __future__ import annotations

import os
from typing import Optional

# -----------------------------------------------------------------------------#
# Public API                                                                    #
# -----------------------------------------------------------------------------#
def find_bids_root(start_path: Optional[str] = None) -> str:
    """Return the absolute path to the nearest BIDS root.

    Search starts at *start_path* (if provided) or the current working
    directory and walks upward until a directory containing
    ``dataset_description.json`` is found.

    Args:
        start_path: Optional starting directory.  When ``None`` the search
            begins in :pyfunc:`os.getcwd`.

    Returns:
        Absolute path to the directory that contains *dataset_description.json*.

    Raises:
        RuntimeError: No BIDS root could be located before reaching the
            filesystem root.
    """
    path = os.path.abspath(start_path or os.getcwd())

    while True:
        if os.path.exists(os.path.join(path, "dataset_description.json")):
            return path

        parent = os.path.dirname(path)
        if parent == path:  # reached filesystem root
            raise RuntimeError(
                "Could not locate BIDS root: no dataset_description.json found above "
                f"{start_path or os.getcwd()}"
            )
        path = parent
