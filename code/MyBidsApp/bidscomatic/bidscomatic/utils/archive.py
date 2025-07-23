"""
Helpers for identifying study archives.

This module contains *pure* utility code used by several pipelines that need
to decide whether a given file path points to a supported compressed archive.
Keeping the predicate here avoids code duplication in:

* The **unzip** pipeline (runtime extraction).
* Future validation or GUI layers.
* Unit-tests that fabricate synthetic archives.

The logic purposefully remains extremely cheap: a simple suffix comparison
covers all practical cases and avoids expensive `tarfile` / `zipfile` probing
during directory scans.
"""

from __future__ import annotations

from pathlib import Path

#: Recognised archive endings **in order of preference**.
#: The list is sorted longest-to-shortest so a basename such as
#: ``study.attached.tar.gz`` matches ``.tar.gz`` before the generic ``.gz``.
_ARCHIVE_SUFFIXES: tuple[str, ...] = (
    ".tar.gz",
    ".tar.bz2",
    ".tar",
    ".tgz",
    ".tbz",
    ".zip",
)


def looks_like_archive(path: Path) -> bool:
    """Return *True* when *path* resembles a compressed study archive.

    A file qualifies as an archive when its **basename** ends with one of the
    suffixes in :data:`_ARCHIVE_SUFFIXES`. The check is case-insensitive and
    tolerant of additional middle segments such as hashes or ``.attached``::

        >>> looks_like_archive(Path("baseline_1.AD3A0FEA.tar"))
        True
        >>> looks_like_archive(Path("something.attached.tar.gz"))
        True
        >>> looks_like_archive(Path("image.123E4567.tgz"))
        True
        >>> looks_like_archive(Path("notes.txt"))
        False

    Args:
        path: Filesystem path to test.

    Returns:
        ``True`` if *path* is a **file** and its name ends with a recognised
        archive suffix. Otherwise ``False``.
    """
    if not path.is_file():
        # Directories or missing paths never count as archives.
        return False

    lower_name = path.name.lower()         # Basename only → faster I/O
    return any(lower_name.endswith(suf) for suf in _ARCHIVE_SUFFIXES)
