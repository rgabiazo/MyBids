"""
Package-level logging configuration.

* Rich console output (colourised, nicely formatted).
* Rotating **JSON** log file inside ``code/logs/`` when a dataset root is
  known (or ``$BIDSCOMATIC_LOG_DIR`` when set).
* Optional plain-text mirror controlled via ``--save-logfile`` on the CLI.

The public helper :func:`setup_logging` wires everything and should be the
sole entry-point used by sub-commands.
"""

from __future__ import annotations

import atexit
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

import structlog
from rich.logging import RichHandler
from structlog.dev import ConsoleRenderer as StructlogConsoleRenderer
from structlog.stdlib import LoggerFactory

__all__ = [
    "setup_logging",
    "_get_file_handler",  # kept for backward compatibility
]


# --------------------------------------------------------------------------- #
# Internal helpers – file-based handlers                                      #
# --------------------------------------------------------------------------- #
def _json_file_handler(dataset_root: Path | None, level: int) -> logging.Handler:
    """Return a rotating *JSON* file handler.

    Args:
        dataset_root: BIDS dataset root; determines the log directory when
            ``BIDSCOMATIC_LOG_DIR`` is not set.
        level: Log-level for the handler.

    Returns:
        Configured :class:`logging.Handler` writing rotating JSON logs either
        under ``dataset_root/code/logs``, the directory specified via the
        ``BIDSCOMATIC_LOG_DIR`` environment variable or the package-local
        ``logs/`` folder when no dataset root is supplied.
    """
    env_dir = os.environ.get("BIDSCOMATIC_LOG_DIR")

    if env_dir:
        logdir = Path(env_dir).expanduser()
    elif dataset_root is not None:
        logdir = dataset_root / "code" / "logs"
    else:
        logdir = Path(__file__).resolve().parents[1] / "logs"
    logdir.mkdir(parents=True, exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        filename=logdir / "bidscomatic.log",
        maxBytes=5_000_000,  # ~5 MB before rollover
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(level)
    return handler


def _plain_text_file_handler(
    path: Optional[Path], level: int
) -> logging.Handler | None:
    """Return a plain-text file handler or *None* when *path* is *None*.

    Args:
        path: Destination file.
        level: Log-level for the handler.

    Returns:
        Configured handler or *None* when no log file is requested.
    """
    if path is None:
        return None

    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    handler = logging.FileHandler(path, encoding="utf-8", mode="a")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    # Ensure the buffer is flushed on interpreter exit.
    atexit.register(handler.close)
    return handler


# Back-compat façade expected by legacy imports inside the CLI layer.
def _get_file_handler(path: Optional[Path], level: int = logging.INFO):
    """Shim that delegates to :func:`_plain_text_file_handler`."""
    return _plain_text_file_handler(path, level)


# --------------------------------------------------------------------------- #
# Public API – main entry-point                                               #
# --------------------------------------------------------------------------- #
def setup_logging(
    *,
    dataset_root: Path | None = None,
    verbose: bool = False,
    debug: bool = False,
    force_info: bool = False,
    extra_text_log: Optional[Path] = None,
) -> None:
    """Configure rich console logging and optional file mirrors.

    Args:
        dataset_root: BIDS dataset root used to determine JSON log location.
        verbose: Emit INFO-level messages to the console.
        debug: Emit DEBUG-level messages plus JSON *and* rich tracebacks.
        force_info: Force INFO level even when both *verbose* and *debug* are
            *False* (used by early-stage commands).
        extra_text_log: Optional path for a plain-text mirror of console output.

    Raises:
        ValueError: If *dataset_root* exists but is not a directory.
    """
    # Determine console log-level ------------------------------------------------
    console_lvl = (
        logging.DEBUG
        if debug
        else logging.INFO if verbose or force_info else logging.WARNING
    )
    file_lvl = logging.DEBUG if debug else logging.INFO

    handlers: list[logging.Handler] = []

    # --- Rich or minimal console handler ---------------------------------------
    if force_info and not (verbose or debug):
        # Minimal console without rich-markup (used by unzip/convert previews)
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(console_lvl)
        console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    else:
        console = RichHandler(
            level=console_lvl,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
        )
    handlers.append(console)

    # --- Rotating JSON log inside the dataset ----------------------------------
    handlers.append(_json_file_handler(dataset_root, file_lvl))

    # --- Optional plain-text logfile -------------------------------------------
    txt_handler = _plain_text_file_handler(extra_text_log, console_lvl)
    if txt_handler:
        handlers.append(txt_handler)

    # --- Configure root logger --------------------------------------------------
    logging.basicConfig(
        level=logging.DEBUG,  # root logger stays at DEBUG
        handlers=handlers,
        format="%(message)s",  # Rich/structlog handle formatting
    )

    # --- structlog binds --------------------------------------------------------
    structlog.configure(
        processors=[
            *(
                []
                if force_info and not (verbose or debug)
                else [
                    structlog.processors.TimeStamper(fmt="iso"),
                    structlog.processors.add_log_level,
                ]
            ),
            (
                StructlogConsoleRenderer()
                if verbose or debug or force_info
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(console_lvl),
        logger_factory=LoggerFactory(),
    )
