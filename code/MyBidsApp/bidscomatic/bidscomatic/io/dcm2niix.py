"""Safe wrapper around the *dcm2niix* command-line tool.

The helper runs *dcm2niix* in a subprocess, captures its output, and returns
every file created during conversion.  A single automatic retry is performed
with the Siemens-specific ``-m y`` flag when the first attempt fails due to
the *“No valid DICOM images were found”* error.

The implementation purposefully avoids changing environment variables or
global state.  All paths are handled as :class:`pathlib.Path` objects and are
resolved to absolute paths before execution.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Sequence

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------
def _which_dcm2niix() -> str:
    """Return the absolute path to *dcm2niix* or raise if it is not on *PATH*."""
    exe = shutil.which("dcm2niix")
    if not exe:
        raise RuntimeError(
            "dcm2niix not found on $PATH – install it or expose the binary."
        )
    return exe


def _build_cmd(
    src: Path,
    dst: Path,
    *,
    compress: bool,
    fname_tmpl: str,
    bids_sidecar: bool,
    extra_flags: Sequence[str] | None,
    additional: Sequence[str] | None = None,
) -> list[str]:
    """Compose the *dcm2niix* command as a list suitable for ``subprocess.run``.

    Args:
        src: Directory that contains DICOM files from exactly one scanner series.
        dst: Output directory (created by the caller).
        compress: If *True*, write ``.nii.gz``; otherwise produce plain ``.nii``.
        fname_tmpl: Value passed to ``dcm2niix -f``.
        bids_sidecar: When *True*, request BIDS-style JSON sidecars (``-b y``).
        extra_flags: Additional flags appended verbatim to the command.
        additional: Optional flags appended *after* ``extra_flags``—
            used internally for the Siemens retry.

    Returns:
        list[str]: The complete argument vector for *dcm2niix*.
    """
    cmd: list[str] = [
        _which_dcm2niix(),
        "-z",
        "y" if compress else "n",
        "-f",
        fname_tmpl,
        "-o",
        str(dst),
    ]

    # Side-car control
    if bids_sidecar:
        cmd += ["-b", "y"]

    # Flags provided by the caller go first …
    if extra_flags:
        cmd.extend(extra_flags)

    # … followed by any internal additions (e.g., “-m y” on retry)
    if additional:
        cmd.extend(additional)

    # Source directory is always the final token
    cmd.append(str(src))
    return cmd


# ---------------------------------------------------------------------------
# public helper
# ---------------------------------------------------------------------------
def run_dcm2niix(
    src: Path,
    dst: Path,
    *,
    compress: bool = True,
    fname_tmpl: str = "%p_%s",
    bids_sidecar: bool = True,
    extra_flags: Sequence[str] | None = None,
) -> List[Path]:
    """Convert one DICOM *series directory* into NIfTI/JSON files.

    Args:
        src: Path to a directory that contains only DICOM slices belonging to
            a single scanner series.
        dst: Destination directory.  Created with ``parents=True`` when needed.
        compress: Write ``.nii.gz`` when *True*; otherwise emit plain ``.nii``.
        fname_tmpl: Template string forwarded to ``dcm2niix -f``.
        bids_sidecar: Generate BIDS-compatible JSON files when *True*.
        extra_flags: Additional flags appended verbatim to the command.

    Returns:
        List[Path]: Sorted list of all files that were created in *dst*.

    Raises:
        ValueError: When *src* is not a directory.
        RuntimeError: When *dcm2niix* is missing or terminates with a non-zero
            exit status **after** the automatic retry (if any).
    """
    if not src.is_dir():
        raise ValueError(f"{src} is not a directory")

    # Ensure the output directory exists before conversion starts
    dst.mkdir(parents=True, exist_ok=True)

    # Snapshot directory contents *before* running dcm2niix
    before = {p.resolve() for p in dst.iterdir()}

    # ────────────────────── first attempt ────────────────────────────────
    cmd = _build_cmd(
        src,
        dst,
        compress=compress,
        fname_tmpl=fname_tmpl,
        bids_sidecar=bids_sidecar,
        extra_flags=extra_flags,
    )
    log.debug("dcm2niix cmd: %s", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)

    # ─────────────────── automatic Siemens retry ─────────────────────────
    err_text = (res.stdout + res.stderr).lower()
    needs_retry = (
        res.returncode != 0
        and "no valid dicom images were found" in err_text
        and "-m" not in cmd
    )
    if needs_retry:
        log.warning('dcm2niix could not read "%s" – retrying with "-m y"', src)
        cmd_retry = _build_cmd(
            src,
            dst,
            compress=compress,
            fname_tmpl=fname_tmpl,
            bids_sidecar=bids_sidecar,
            extra_flags=extra_flags,
            additional=["-m", "y"],
        )
        log.debug("dcm2niix retry cmd: %s", " ".join(cmd_retry))
        res = subprocess.run(cmd_retry, capture_output=True, text=True)

    # ───────────────────────── error handling ────────────────────────────
    if res.returncode != 0:
        # Bubble up a concise yet informative error.
        raise RuntimeError(
            f"dcm2niix failed for {src}\n"
            f"stdout:\n{res.stdout}\n"
            f"stderr:\n{res.stderr}"
        )

    # ─────────────────────── collect new files ───────────────────────────
    after = {p.resolve() for p in dst.iterdir()}
    produced = sorted(after - before)
    return produced
