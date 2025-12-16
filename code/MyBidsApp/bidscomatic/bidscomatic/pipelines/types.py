"""
Typed, immutable value objects that circulate between pipeline stages.

The module depends only on the Python standard library and *pydantic* so that
it can be imported early, even in lightweight environments that do not yet
have heavy scientific packages available.

Every class inherits from :class:`pydantic.BaseModel` with ``frozen=True``
to guarantee hash-ability and prevent accidental mutation once the objects
have been created.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import BaseModel


class SubjectSession(BaseModel, frozen=True):
    """Compound identifier that groups subject and session information.

    Attributes
    ----------
    root
        Absolute path to the BIDS dataset root.  Including the path directly
        avoids repeatedly passing it around between helpers.
    sub
        Subject identifier, e.g. ``"sub-001"``.
    ses
        Session identifier (optional), e.g. ``"ses-01"``.  *None* for
        single-session acquisitions.
    """

    root: Path
    sub: str
    ses: str | None = None


class Dcm2NiixResult(BaseModel, frozen=True):
    """Return object from a single :pyfunc:`dcm2niix` conversion run.

    Attributes
    ----------
    src_dir
        Directory that contained the original DICOM series.
    out_dir
        Destination directory created by *dcm2niix*.
    files
        All files produced by the conversion, including NIfTI images and
        JSON side-cars, in the order *dcm2niix* emitted them.
    """

    src_dir: Path
    out_dir: Path
    files: list[Path]


class UnzipResult(BaseModel, frozen=True):
    """Summary object returned by :pyfunc:`bidscomatic.pipelines.unzip.unzip_archives`.

    The structure is intentionally minimal so that it can be JSON-serialised
    for log files or deferred post-processing.

    Attributes
    ----------
    src
        Path argument originally supplied to *unzip_archives*.
    archive_dirs
        Directories that contained at least one processed archive.
    archives
        Concrete archive files that were unpacked.  Empty when *src* no longer
        contains archives but *unzip_archives* still performed stray-folder
        discovery.
    dcm_roots
        Top-level directories that now hold raw DICOM slices.  The list is
        consumed by destructive helpers such as
        :pyfunc:`bidscomatic.utils.cleanup.delete_dcm_roots`.
    """

    # Path that was scanned (single file or directory tree)
    src: Path

    # First-level directories that received extracted content
    archive_dirs: list[Path]

    # Additional metadata collected during v1.1+
    archives: list[Path] = []        # every *.zip / *.tar processed
    dcm_roots: list[Path] = []       # top-level DICOM dirs discovered


def discover_subject_sessions(
    root: Path,
    *,
    filter_sub: Iterable[str] | None = None,
    filter_ses: Iterable[str] | None = None,
) -> List[SubjectSession]:
    """Discover subject/session combinations inside a BIDS dataset.

    This helper provides the canonical behaviour expected by CLI commands:
    * If *filter_sub* is omitted, all ``sub-*`` folders under *root* are used.
    * If *filter_ses* is omitted:
        - If a subject contains ``ses-*`` folders, each is emitted.
        - Otherwise a session-less entry (``ses=None``) is emitted.
    * If *filter_ses* is provided, the given sessions are paired with every
      selected subject.

    The helper accepts identifiers with or without ``sub-`` / ``ses-`` prefixes.

    Args:
        root: Dataset root directory.
        filter_sub: Optional iterable of subject identifiers.
        filter_ses: Optional iterable of session identifiers.

    Returns:
        A sorted list of :class:`SubjectSession` objects.
    """

    def _norm(value: str, prefix: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(f"empty identifier for {prefix}")
        return value if value.startswith(prefix) else f"{prefix}{value}"

    if filter_sub:
        subs = [_norm(s, "sub-") for s in filter_sub]
    else:
        subs = sorted(p.name for p in root.glob("sub-*") if p.is_dir())

    sessions: list[SubjectSession] = []
    for sub in subs:
        sub_dir = root / sub
        if not sub_dir.exists():
            continue

        if filter_ses:
            sess = [_norm(se, "ses-") for se in filter_ses]
            for ses in sess:
                sessions.append(SubjectSession(root=root, sub=sub, ses=ses))
            continue

        ses_dirs = sorted(p.name for p in sub_dir.glob("ses-*") if p.is_dir())
        if ses_dirs:
            for ses in ses_dirs:
                sessions.append(SubjectSession(root=root, sub=sub, ses=ses))
        else:
            sessions.append(SubjectSession(root=root, sub=sub, ses=None))

    # De-duplicate while preserving stable order, then sort.
    seen: set[tuple[str, Optional[str]]] = set()
    uniq: list[SubjectSession] = []
    for ss in sessions:
        key = (ss.sub, ss.ses)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(ss)

    return sorted(uniq, key=lambda s: (s.sub, s.ses or ""))
