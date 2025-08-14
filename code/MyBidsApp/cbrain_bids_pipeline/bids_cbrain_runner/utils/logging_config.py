"""
Centralised logger configuration for command‑line utilities.

The helper exposed here standardises how all *bids_cbrain_runner* entry‑points
initialise the Python :pyclass:`logging` hierarchy.

Design goals
============
* **Single point of truth** – a shared configuration avoids diverging logging
  behaviour across sub‑commands.
* **Noise control** – Paramiko (SSH/SFTP backend) emits verbose DEBUG logs that
  are rarely useful during regular operation.  The helper therefore downgrades
  Paramiko’s default level to ``WARNING`` unless the caller explicitly requests
  verbose output.
* **Compatibility** – only stdlib logging is used; no third‑party
  dependencies are introduced.

Typical usage::

    from bids_cbrain_runner.utils.logging_config import setup_logging

    setup_logging(verbose=args.debug_logs)
"""

from __future__ import annotations

import logging

__all__ = ["setup_logging"]

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    """Initialise root logger and tame noisy third‑party libraries.

    Args:
        verbose: When *True*, emit DEBUG‑level messages to stderr; otherwise
            restrict console output to ``INFO`` and above.

    Returns:
        ``None`` – the function mutates the global logging configuration in
        place.
    """
    # Capture *all* messages internally so that child loggers can escalate to
    # DEBUG without further configuration.
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Console handler – human‑readable single‑line formatting -------------------
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root_logger.addHandler(console)

    # Third‑party libraries ------------------------------------------------------
    paramiko_logger = logging.getLogger("paramiko")
    paramiko_logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
