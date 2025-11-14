"""Docker helpers."""

from __future__ import annotations

import platform
import subprocess
import structlog

log = structlog.get_logger()


def detect_platform(image: str) -> str | None:
    """Return a Docker platform string supported by ``image`` when available.

    Args:
        image: Name of the container image to inspect via ``docker imagetools``.

    Returns:
        A platform string suitable for ``--platform`` or ``None`` to defer to
        Docker's native selection.

    The function inspects the manifest of ``image`` to select an appropriate
    ``--platform`` argument. On ``arm64`` hosts the helper favours an
    ``arm64`` variant when available and otherwise falls back to ``amd64``.
    On ``x86_64`` hosts ``None`` is returned so Docker picks the native
    architecture. Any probing errors are treated as if the image lacked an
    ``arm64`` manifest.
    """
    host = platform.machine()
    try:  # pragma: no cover - best-effort helper
        out = subprocess.check_output(
            ["docker", "buildx", "imagetools", "inspect", image],
            text=True,
        )
    except Exception as exc:  # pragma: no cover
        log.info("docker.platform_probe_failed", error=str(exc))
        return "linux/amd64" if host == "arm64" else None
    if host == "arm64":
        return "linux/arm64" if "linux/arm64" in out else "linux/amd64"
    return None
