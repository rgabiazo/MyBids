"""Build a Docker command for dcm4che ``findscu``.

This module only assembles the command string. Execution occurs in
``dicomatic.query.findscu.run_findscu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional


def build_findscu(
    container: str,
    bind: str,
    server: str,
    port: str,
    tls: str,
    username: str,
    password: str,
    query_tags: List[str],
    filters: Optional[Dict[str, str]] = None,
) -> List[str]:
    """Return a CLI invocation for ``findscu`` inside a Docker image.

    Args:
        container: Docker image name, for example ``"cfmm2tar"``.
        bind: Local bind option supplied to dcm4che (for example ``"DEFAULT"``).
        server: Remote DICOM ``AET@hostname`` string.
        port: Remote DICOM port number as a string.
        tls: TLS mode; ``"aes"``, ``"ssl"``, or ``"none"``.
        username: DICOM username.
        password: DICOM password.
        query_tags: DICOM attribute keywords requested via ``-r``.
        filters: Optional mapping of keyword to match value passed as
            ``-m <tag>=<value>`` arguments.

    Returns:
        list[str]: Command-line tokens suitable for ``subprocess.run``.
    """
    cmd: List[str] = [
        "docker",
        "run",
        "--rm",
        "--entrypoint",
        "/opt/dcm4che/bin/findscu",
        container,
        "--bind",
        bind,
        "--connect",
        f"{server}:{port}",
        f"--tls-{tls}",
        "--user",
        username,
        "--user-pass",
        password,
        "-L",
        "STUDY",
    ]

    # Request each attribute via repeated -r flags
    for tag in query_tags:
        cmd.extend(["-r", tag])

    # Apply C-FIND match filters when provided
    if filters:
        for tag, val in filters.items():
            if val not in (None, ""):
                cmd.extend(["-m", f"{tag}={val}"])

    return cmd
