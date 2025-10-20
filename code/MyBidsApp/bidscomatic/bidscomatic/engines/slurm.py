from __future__ import annotations

"""Skeleton Slurm execution engine."""

import subprocess
from typing import Mapping, Sequence
import structlog

from .base import ExecutionEngine

log = structlog.get_logger()


class SlurmEngine(ExecutionEngine):
    """Run containerised tools via ``srun``.

    This is a minimal placeholder to illustrate how additional execution
    back-ends could be integrated.  It simply wraps ``docker run`` with
    ``srun`` so callers can experiment on HPC systems.
    """

    def run(
        self,
        image: str,
        args: Sequence[str],
        *,
        volumes: Mapping[str, str],
        env: Mapping[str, str],
        entrypoint: str | None = None,
    ) -> int:
        """Execute *image* with ``srun`` while propagating runtime context.

        Args:
            image: Container reference passed to ``docker run``.
            args: Positional arguments forwarded to the container.
            volumes: Mapping of host paths to container mount points.
            env: Environment variables injected into the container.
            entrypoint: Optional command used to override the image default.

        Returns:
            Always returns ``0`` because :func:`subprocess.run` raises on
            failure when ``check=True``.
        """
        cmd: list[str] = ["srun", "docker", "run", "--rm", "-t"]
        for host, guest in volumes.items():
            cmd += ["-v", f"{host}:{guest}"]
        for key, value in env.items():
            cmd += ["-e", f"{key}={value}"]
        if entrypoint:
            cmd += ["--entrypoint", entrypoint]
        cmd.append(image)
        cmd.extend(args)
        log.info("slurm.run", image=image, args=args)
        subprocess.run(cmd, check=True)
        return 0
