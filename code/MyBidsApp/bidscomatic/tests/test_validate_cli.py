from pathlib import Path
import os
import subprocess

CLI = ["python", "-m", "bidscomatic.cli", "validate"]


def _make_validator(path: Path, exit_code: int = 0) -> None:
    """Write a stub ``bids-validator`` executable for CLI tests.

    Args:
        path: Destination path for the generated shell script.
        exit_code: Exit status emitted when the stub is executed.
    """
    path.write_text("#!/usr/bin/env bash\necho validator\nexit %d\n" % exit_code)
    path.chmod(0o755)


def test_validate_cli_success(tmp_path: Path) -> None:
    """Verify validate CLI success behavior."""
    ds = tmp_path / "ds"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_validator(bindir / "bids-validator", 0)

    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}" + env.get("PATH", "")

    result = subprocess.run(CLI, cwd=ds, capture_output=True, text=True, env=env)
    assert result.returncode == 0
    assert "BIDS validation passed" in result.stdout


def test_validate_cli_failure(tmp_path: Path) -> None:
    """Verify validate CLI failure behavior."""
    ds = tmp_path / "ds2"
    ds.mkdir()
    (ds / "dataset_description.json").write_text("{}")

    bindir = tmp_path / "bin"
    bindir.mkdir()
    _make_validator(bindir / "bids-validator", 1)

    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}" + env.get("PATH", "")

    result = subprocess.run(CLI, cwd=ds, capture_output=True, text=True, env=env)
    assert result.returncode != 0
    assert "BIDS validation failed" in result.stderr
