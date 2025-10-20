from pathlib import Path
import subprocess

from click.testing import CliRunner

from bidscomatic.cli import main as cli_main
from bidscomatic.utils import fsl
import json
import pytest

from ._mcflirt import MCFLIRT_STDOUT


@pytest.fixture(autouse=True)
def mock_fsl(monkeypatch):
    """Monkeypatch the FSL runner used by preprocess CLI tests.

    Args:
        monkeypatch: Pytest fixture that overrides :func:`bidscomatic.utils.fsl.run_cmd`.
    """
    def _run(
        cmd,
        *,
        capture=False,
        on_stdout=None,
        suppress_final_result_from_live=False,
    ):
        cmd0 = cmd[0]
        if cmd0 == "mcflirt":
            base = Path(cmd[4])
            base.with_suffix(".nii.gz").touch()
            base.with_suffix(".par").touch()
            output = MCFLIRT_STDOUT
            live = output.split("Final result:")[0]
            if capture:
                if on_stdout is not None:
                    for line in live.splitlines():
                        if line:
                            on_stdout(line)
                else:
                    print(live, end="")
                result = subprocess.CompletedProcess(cmd, 0, stdout=output)
                setattr(result, "streamed", True)
                return result
            print(live, end="")
            return subprocess.CompletedProcess(cmd, 0, output, "")
        elif cmd0 == "fslmaths":
            Path(cmd[-1]).touch()
        elif cmd0 == "flirt":
            Path(cmd[6]).touch()
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(fsl, "run_cmd", _run)


def _make_dataset(root):
    """Populate a minimal dataset for preprocess CLI exercises.

    Args:
        root: Temporary dataset root provided by the ``tmp_path`` fixture.
    """
    (root / "dataset_description.json").write_text("{}")
    fmap = root / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j", "TotalReadoutTime": 0.1})
    )
    func = root / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-assocmemory_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-assocmemory_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-"})
    )
    (func / "sub-001_ses-01_task-rest_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-rest_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-"})
    )


def test_cli_preprocess_creates(tmp_path):
    """Verify CLI preprocess creates behavior."""
    _make_dataset(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["--bids-root", str(tmp_path), "preprocess", "pepolar", "--filter-sub", "001", "--filter-ses", "01"],
    )
    assert result.exit_code == 0, result.output
    output = result.output
    assert "PEPOLAR — Subject: sub-001 | Session: ses-01" in output
    assert "Fieldmaps" in output
    assert "Source BOLD runs (dir=AP" in output
    assert "1) Motion correction — run-01 (dir=AP)" in output
    assert "2) Motion correction — run-02 (dir=AP)" in output
    assert "MCFLIRT stdout (run-01)" in output
    assert "MCFLIRT stdout (run-02)" in output
    assert "Final result" not in output
    assert "✓ Saved motion-corrected time series (run-01)" in output
    assert "✓ Saved motion-corrected time series (run-02)" in output
    assert "Opposite-PE fieldmap derivation" in output
    assert "Final transforms from alignment to ref (FLIRT)" in output
    assert "Transform A" in output
    assert "Transform B" in output
    assert "[ 1.000000  0.000000  0.000000  0.000000 ]" in output
    assert "[ 0.000000  0.000000  0.000000  1.000000 ]" in output
    assert "Done." in output
    assert (
        "…/derivatives/fsl/McFLIRT/sub-001/ses-01/"
        "sub-001_ses-01_dir-AP_run-01_desc-robust_mcf.nii.gz" in output
    )
    assert "Wrote 1 fieldmap(s):" in output
    expect = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.nii.gz"
    assert expect.exists()
    j = json.loads(expect.with_suffix("").with_suffix('.json').read_text())
    assert len(j.get('IntendedFor', [])) == 2
    canon = (
        tmp_path
        / "sub-001"
        / "ses-01"
        / "fmap"
        / "sub-001_ses-01_dir-PA_epi.json"
    )
    meta = json.loads(canon.read_text())
    assert len(meta.get('IntendedFor', [])) == 2


def test_cli_preprocess_task_filter(tmp_path):
    """Verify CLI preprocess task filter behavior."""
    _make_dataset(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "pepolar",
            "--filter-sub",
            "001",
            "--filter-ses",
            "01",
            "--task",
            "assocmemory",
        ],
    )
    assert result.exit_code == 0, result.output
    expect = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.nii.gz"
    j = json.loads(expect.with_suffix("").with_suffix('.json').read_text())
    assert j["IntendedFor"] == [
        "ses-01/func/sub-001_ses-01_task-assocmemory_bold.nii.gz"
    ]
    output = result.output
    assert "Task: assocmemory" in output
    assert "Source BOLD runs (dir=AP" in output
    assert "1) Motion correction — run-01 (dir=AP)" in output


def test_cli_preprocess_use_bids_uri(tmp_path):
    """Verify CLI preprocess USE BIDS URI behavior."""
    _make_dataset(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "pepolar",
            "--filter-sub",
            "001",
            "--filter-ses",
            "01",
            "--use-bids-uri",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    out_json = (
        tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.json"
    )
    meta = json.loads(out_json.read_text())
    assert meta["IntendedFor"] == [
        "bids::sub-001/ses-01/func/sub-001_ses-01_task-assocmemory_bold.nii.gz",
        "bids::sub-001/ses-01/func/sub-001_ses-01_task-rest_bold.nii.gz",
    ]


def test_cli_preprocess_dry_run(tmp_path):
    """Verify CLI preprocess DRY RUN behavior."""
    _make_dataset(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "pepolar",
            "--filter-sub",
            "001",
            "--filter-ses",
            "01",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    expect = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.nii.gz"
    assert not expect.exists()
    canon = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-PA_epi.json"
    meta = json.loads(canon.read_text())
    assert "IntendedFor" not in meta


def test_cli_preprocess_fsl_failure(tmp_path, monkeypatch):
    """Verify CLI preprocess FSL failure behavior."""
    _make_dataset(tmp_path)

    def fail(cmd, *, capture=False, on_stdout=None, suppress_final_result_from_live=False):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(fsl, "run_cmd", fail)
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["--bids-root", str(tmp_path), "preprocess", "pepolar", "--filter-sub", "001", "--filter-ses", "01"],
    )
    assert result.exit_code != 0
