"""Utilities for file-system–friendly slugs and optional dataset renaming.

The functions in this module are intentionally small and side-effect free
(except for the optional directory rename). They operate on plain
:class:`pathlib.Path` and therefore remain agnostic to the rest of the
*bidscomatic* package.

Notes:
    * All transformations convert input text to ASCII, replace non-word
      characters with a single dash, collapse multiple dashes, and lower-case
      the result by default.
    * ``rename_root_if_needed`` performs a **best-effort** rename. The helper
      first checks whether the target path already exists and, when it does or
      the rename fails, logs the situation and returns the original path
      unchanged.  This avoids platform differences where ``Path.rename`` may
      silently replace an empty directory on POSIX but raise ``FileExistsError``
      on Windows.
"""

from __future__ import annotations

import logging
import errno
import re
import unicodedata
from pathlib import Path
from typing import Optional

__all__ = ["slugify", "rename_root_if_needed"]

# One regular expression is shared by both helpers.
# Matches every character that is **not** a word character or dash.
_SLUG_RE = re.compile(r"[^\w\-]+")


def slugify(
    text: str,
    *,
    fallback: str = "unnamed-study",
    lowercase: bool = True,
) -> str:
    """Return *text* transformed into a URL- and file-safe slug.

    The transformation pipeline is:

    1. **Unicode normalisation** – converts diacritics to plain ASCII.
    2. **Removal of non-ASCII** code points.
    3. Replace every non-word / non-dash character with ``-``.
    4. Collapse runs of multiple dashes.
    5. Convert to lower-case when ``lowercase`` is ``True``.
    6. Substitute *fallback* when the result is empty.

    Args:
        text: Arbitrary input string (UTF-8 or ASCII).
        fallback: Replacement slug when the transformation yields an empty
            string.
        lowercase: When ``True`` (default), return a lower-case slug. When
            ``False`` the original letter case is preserved.

    Returns:
        str: A slug consisting only of ``[A-Za-z0-9_-]`` characters.
        Lower-cased when ``lowercase`` is ``True``.
    """
    # Normalise accented characters and drop the accents (e.g. “é” → “e”).
    ascii_txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    # Replace every disallowed character with a dash.
    slug = _SLUG_RE.sub("-", ascii_txt).strip("-")
    if lowercase:
        slug = slug.lower()
    # Collapse duplicates ("foo--bar" → "foo-bar") and return the result.
    return re.sub("-{2,}", "-", slug) or fallback


def rename_root_if_needed(
    root: Path,
    wanted_name: str,
    *,
    logger: Optional[logging.Logger] = None,
    create_missing_slug: bool = False,
) -> Path:
    """Rename *root* so that its last path component matches *wanted_name*.

    This helper is used by the dataset-initialisation routine to keep the
    directory structure consistent with the study title entered by the
    researcher.

    The function is **idempotent**: if the directory already has the expected
    name, the original :class:`~pathlib.Path` is returned immediately.

    Args:
        root: Existing or planned dataset root. Relative paths are resolved to
            an absolute location; this guarantees that :pyattr:`Path.name` is
            never an empty string.
        wanted_name: Human-readable study title. The function converts it to a
            slug via :func:`slugify`.
        logger: Optional :pymod:`logging` instance. When *None*, the
            module-level logger is used.
        create_missing_slug: If *True* and *root* **does not** exist, the
            function returns the would-be target path without performing any
            I/O. This flag is useful when the caller intends to create the
            directory later.

    Returns:
        pathlib.Path: Either the original *root* (unchanged) or the new,
        renamed path.

    Examples:
        >>> rename_root_if_needed(Path("/data/Study ABC"), "Study ABC")
        PosixPath('/data/Study-ABC')
    """
    log = logger or logging.getLogger(__name__)

    # Make the path absolute to avoid surprises such as Path('.').name == ''.
    root = root.expanduser().resolve()
    wanted_slug = slugify(wanted_name, lowercase=False)

    # Nothing to do when the directory already has the desired slug.
    if root.name == wanted_slug:
        log.info("[naming] Dataset root already matches study name ↳ %s", root.name)
        return root

    # The dataset directory is expected **not** to exist yet.
    if not root.exists():
        if create_missing_slug:
            target = root.with_name(wanted_slug)
            log.info("[naming] %s missing – will create %s instead", root, target)
            return target
        log.debug("[naming] %s does not exist – keeping provided path", root)
        return root

    # Perform the rename and return the new absolute path.
    target = root.with_name(wanted_slug)

    # On POSIX systems ``Path.rename`` will replace ``target`` when it is an
    # empty directory while Windows raises ``FileExistsError``. To ensure a
    # consistent outcome across platforms, this function checks whether the
    # target exists and skips the rename when it is already present.
    if target.exists():
        log.warning("[naming] %s exists – keeping %s", target, root)
        return root

    log.warning(
        "[naming] Root folder '%s' disagrees with study name – renaming to '%s'",
        root.name,
        wanted_slug,
    )
    try:
        root.rename(target)
    except OSError as err:  # pragma: no cover - platform specific
        if err.errno in (errno.EEXIST, errno.ENOTEMPTY):
            log.warning("[naming] %s exists – keeping %s", target, root)
            return root
        raise
    return target
