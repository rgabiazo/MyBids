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
