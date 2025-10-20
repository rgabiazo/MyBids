from bidscomatic.utils.fsl import run_cmd


def test_run_cmd_echo():
    """Verify RUN CMD echo behavior."""
    res = run_cmd(["bash", "-c", "echo hello"])
    assert res.returncode == 0
    assert res.stdout is None
