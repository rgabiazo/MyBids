import subprocess

from bidscomatic.engines.slurm import SlurmEngine

def test_slurm_engine_builds_command(monkeypatch):
    """Verify SLURM engine builds command behavior."""
    called = {}

    def fake_run(cmd, check):
        called['cmd'] = cmd
        called['check'] = check
        class Dummy:
            returncode = 0
        return Dummy()

    monkeypatch.setattr(subprocess, 'run', fake_run)

    eng = SlurmEngine()
    eng.run('img', ['arg'], volumes={'/host': '/guest'}, env={'A': '1'})
    cmd = called['cmd']
    assert cmd[:3] == ['srun', 'docker', 'run']
    assert '-v' in cmd and '/host:/guest' in ' '.join(cmd)
    assert '-e' in cmd and 'A=1' in ' '.join(cmd)
    assert called['check'] is True
