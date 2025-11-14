"""Docker execution engine."""

from __future__ import annotations

import subprocess
from typing import Mapping, Sequence

import structlog
import click

from .base import ExecutionEngine

log = structlog.get_logger()


class DockerEngine(ExecutionEngine):
    """Run tools inside Docker containers."""

    def __init__(self, platform: str | None = None) -> None:
        """Configure the engine.

        Args:
            platform: Optional ``docker --platform`` value to request a
                specific architecture when pulling the image.
        """
        self.platform = platform

    def run(
        self,
        image: str,
        args: Sequence[str],
        *,
        volumes: Mapping[str, str],
        env: Mapping[str, str],
        entrypoint: str | None = None,
    ) -> int:
        """Execute *image* while propagating mounts and environment data.

        Args:
            image: Container reference such as ``my/image:tag``.
            args: Positional arguments forwarded to the container entrypoint.
            volumes: Mapping of host paths to mount inside the container.
            env: Environment variables to expose in the container.
            entrypoint: Optional command overriding the image entrypoint.

        Returns:
            ``0`` on success.

        Raises:
            click.ClickException: If Docker exits with a non-zero status.
        """
        cmd: list[str] = ["docker", "run", "--rm", "-t"]
        if self.platform:
            cmd += ["--platform", self.platform]
        for host, guest in volumes.items():
            cmd += ["-v", f"{host}:{guest}"]
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
        if entrypoint:
            cmd += ["--entrypoint", entrypoint]
        cmd.append(image)
        cmd.extend(args)
        log.info("docker.run", image=image, args=args)
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            log.error("docker.failed", image=image, returncode=exc.returncode)
            raise click.ClickException(
                f"Docker exited with status {exc.returncode}"
            ) from exc
        return 0
