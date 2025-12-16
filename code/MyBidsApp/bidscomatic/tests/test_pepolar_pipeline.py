from pathlib import Path
import subprocess

from bidscomatic.config.pepolar import PepolarConfig
from bidscomatic.pipelines.pepolar import (
    _extract_final_matrix,
    derive_pepolar_fieldmaps,
)
from bidscomatic.pipelines.types import SubjectSession
from bidscomatic.utils import fsl
from bidscomatic.utils.errors import PePolarError
import json
import pytest

from ._mcflirt import EXPECTED_IDENTITY_MATRIX, MCFLIRT_STDOUT


@pytest.fixture(autouse=True)
def mock_fsl(monkeypatch):
    """Stub out FSL commands to avoid external dependencies.

    Args:
        monkeypatch: Pytest fixture that replaces :func:`bidscomatic.utils.fsl.run_cmd`.
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
            if capture:
                live = output.split("Final result:")[0]
                if on_stdout is not None:
                    for line in live.splitlines():
                        if line:
                            on_stdout(line)
                else:
                    print(live, end="")
                result = subprocess.CompletedProcess(cmd, 0, stdout=output)
                setattr(result, "streamed", True)
                return result
            print(output.split("Final result:")[0], end="")
            return subprocess.CompletedProcess(cmd, 0, output, "")
        elif cmd0 == "fslmaths":
            Path(cmd[-1]).touch()
        elif cmd0 == "flirt":
            Path(cmd[6]).touch()
            if capture:
                return subprocess.CompletedProcess(cmd, 0, stdout=MCFLIRT_STDOUT)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(fsl, "run_cmd", _run)


def _make_dataset(root: Path) -> None:
    """Create a minimal dataset with a canonical PA fieldmap.

    Args:
        root: Dataset root directory prepared by the test fixture.
    """
    (root / "dataset_description.json").write_text("{}")
    fmap = root / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j", "TotalReadoutTime": 0.1})
    )


def test_extract_final_matrix_strips_trailing_block():
    """Verify extract final matrix strips trailing block behavior."""
    matrix, cleaned = _extract_final_matrix(MCFLIRT_STDOUT + "extra\n")
    assert matrix == EXPECTED_IDENTITY_MATRIX
    assert "Final result" not in cleaned
    assert cleaned.startswith("Processed data will be saved")
    assert cleaned.endswith("extra")


def _make_with_func(root: Path, trt: float = 0.1) -> None:
    """Populate the dataset with a single functional run and metadata.

    Args:
        root: Dataset root directory prepared by the test fixture.
        trt: Total readout time stored in the functional JSON sidecar.
    """
    _make_dataset(root)
    func = root / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-test_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-test_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-", "TotalReadoutTime": trt})
    )


def test_derive_creates_missing(tmp_path):
    """Verify derive creates missing behavior."""
    _make_with_func(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    cfg = PepolarConfig(dry_run=False)
    out = derive_pepolar_fieldmaps(tmp_path, ss, cfg)
    expect = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.nii.gz"
    assert expect in out
    assert expect.exists()


def _make_with_runs(root: Path) -> None:
    """Create a dataset with two BOLD runs for derivative tests.

    Args:
        root: Dataset root directory prepared by the test fixture.
    """
    _make_dataset(root)
    func = root / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    for run in ("01", "02"):
        bold = func / f"sub-001_ses-01_run-{run}_task-test_bold.nii.gz"
        bold.touch()
        (bold.with_suffix("").with_suffix(".json")).write_text(
            json.dumps({"PhaseEncodingDirection": "j-", "TotalReadoutTime": 0.1})
        )


def _make_sessionless(root: Path) -> None:
    """Create a sessionless dataset with matching fieldmaps.

    Args:
        root: Dataset root directory prepared by the test fixture.
    """
    (root / "dataset_description.json").write_text("{}")
    fmap = root / "sub-RG" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-RG_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-RG_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j", "TotalReadoutTime": 0.2})
    )
    func = root / "sub-RG" / "func"
    func.mkdir(parents=True)
    (func / "sub-RG_task-6cat_bold.nii.gz").touch()
    (func / "sub-RG_task-6cat_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-"})
    )


def test_derive_sessionless(tmp_path):
    """Verify derive sessionless behavior."""
    _make_sessionless(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-RG", ses=None)]
    cfg = PepolarConfig(dry_run=False)
    out = derive_pepolar_fieldmaps(tmp_path, ss, cfg)
    expect = tmp_path / "sub-RG" / "fmap" / "sub-RG_dir-AP_epi.nii.gz"
    assert expect in out
    js = json.loads(expect.with_suffix("").with_suffix('.json').read_text())
    assert js["IntendedFor"] == ["func/sub-RG_task-6cat_bold.nii.gz"]


def test_missing_canonical_fieldmap(tmp_path):
    """Verify missing canonical fieldmap behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_derivative_output_structure(tmp_path, capsys):
    """Verify derivative output structure behavior."""
    _make_with_runs(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    captured = capsys.readouterr().out
    assert "McFLIRT v 2.0 - FMRI motion correction" in captured
    assert "Motion correction — run-01 (dir=AP)" in captured
    assert "Motion correction — run-02 (dir=AP)" in captured
    assert "MCFLIRT stdout (run-01)" in captured
    assert "MCFLIRT stdout (run-02)" in captured
    assert "Final result" not in captured
    assert "✓ Saved motion-corrected time series (run-01)" in captured
    assert "✓ Saved motion-corrected time series (run-02)" in captured
    assert "Opposite-PE fieldmap derivation" in captured
    assert "Final transforms from alignment to ref (FLIRT)" in captured
    assert "Transform A" in captured
    assert "Transform B" in captured
    assert "Transform C" in captured
    assert "[ 1.000000  0.000000  0.000000  0.000000 ]" in captured
    assert "[ 0.000000  0.000000  0.000000  1.000000 ]" in captured
    deriv = (
        tmp_path
        / "derivatives"
        / "fsl"
        / "McFLIRT"
        / "sub-001"
        / "ses-01"
    )
    prefix = "sub-001_ses-01_dir-AP"
    assert (deriv / f"{prefix}_from-func_desc-opp-selection_table.tsv").exists()
    assert (deriv / f"{prefix}_desc-qa_log.txt").exists()
    assert (deriv / "_robust_means" / f"{prefix}_run-01_desc-mean.nii.gz").exists()
    assert (deriv / "_robust_aligned" / f"{prefix}_run-02_desc-to-ref.nii.gz").exists()
    assert (deriv / f"{prefix}_run-01_desc-robust_mcf.nii.gz").exists()
    assert (deriv / f"{prefix}_desc-robust_mean.nii.gz").exists()


def test_canonical_json_updated(tmp_path):
    """Verify canonical JSON updated behavior."""
    _make_with_runs(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    canon_json = (
        tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-PA_epi.json"
    )
    meta = json.loads(canon_json.read_text())
    assert meta["IntendedFor"] == [
        "ses-01/func/sub-001_ses-01_run-01_task-test_bold.nii.gz",
        "ses-01/func/sub-001_ses-01_run-02_task-test_bold.nii.gz",
    ]
    assert meta["TotalReadoutTime"] == 0.1


def test_derivative_sessionless(tmp_path):
    """Verify derivative sessionless behavior."""
    _make_sessionless(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-RG", ses=None)]
    derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    deriv = tmp_path / "derivatives" / "fsl" / "McFLIRT" / "sub-RG"
    prefix = "sub-RG_dir-AP"
    assert (deriv / f"{prefix}_from-func_desc-opp-selection_table.tsv").exists()


def test_missing_canonical_sidecar(tmp_path):
    """Verify missing canonical sidecar behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_missing_phase_encoding(tmp_path):
    """Verify missing phase encoding behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-PA_epi.json").write_text(json.dumps({}))
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_both_directions_present(tmp_path):
    """Verify both directions present behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j", "TotalReadoutTime": 0.1})
    )
    (fmap / "sub-001_ses-01_dir-AP_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-AP_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-", "TotalReadoutTime": 0.1})
    )
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    out = derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    assert out == []


def test_no_functionals_raises(tmp_path):
    """When no func/ directory exists, pepolar cannot derive an opposite EPI."""
    _make_dataset(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_dry_run(tmp_path):
    """Verify DRY RUN behavior."""
    _make_with_func(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    cfg = PepolarConfig(dry_run=True)
    out_paths = derive_pepolar_fieldmaps(tmp_path, ss, cfg)
    out = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.nii.gz"
    assert out in out_paths
    assert not out.exists()


def test_use_bids_uri(tmp_path):
    """Verify USE BIDS URI behavior."""
    _make_with_func(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    cfg = PepolarConfig(use_bids_uri=1)
    derive_pepolar_fieldmaps(tmp_path, ss, cfg)
    js = json.loads(
        (tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.json").read_text()
    )
    assert js["IntendedFor"] == [
        "bids::sub-001/ses-01/func/sub-001_ses-01_task-test_bold.nii.gz"
    ]


def test_mismatched_trt(tmp_path):
    """Verify mismatched TRT behavior."""
    _make_with_func(tmp_path, trt=0.2)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_missing_func_sidecar(tmp_path):
    """Verify missing func sidecar behavior."""
    _make_dataset(tmp_path)
    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-test_bold.nii.gz").touch()
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def _make_no_trt_canon(root: Path) -> None:
    """Create a dataset where the canonical fieldmap lacks readout time.

    Args:
        root: Dataset root directory prepared by the test fixture.
    """
    (root / "dataset_description.json").write_text("{}")
    fmap = root / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j"})
    )
    func = root / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-test_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-test_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-", "TotalReadoutTime": 0.2})
    )


def test_canonical_missing_trt_uses_bold(tmp_path):
    """Verify canonical missing TRT uses BOLD behavior."""
    _make_no_trt_canon(tmp_path)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    out_json = (
        tmp_path
        / "sub-001"
        / "ses-01"
        / "fmap"
        / "sub-001_ses-01_dir-AP_epi.json"
    )
    meta = json.loads(out_json.read_text())
    assert meta["TotalReadoutTime"] == 0.2


def test_invalid_phase_encoding_canonical(tmp_path):
    """Verify invalid phase encoding canonical behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "bogus", "TotalReadoutTime": 0.1})
    )
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_invalid_phase_encoding_bold(tmp_path):
    """Verify invalid phase encoding BOLD behavior."""
    _make_dataset(tmp_path)
    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-test_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-test_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "oops"})
    )
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_fsl_commands_invoked(tmp_path, monkeypatch):
    """Verify FSL commands invoked behavior."""
    _make_with_runs(tmp_path)
    calls: list[str] = []

    def record(
        cmd,
        *,
        capture=False,
        on_stdout=None,
        suppress_final_result_from_live=False,
    ):
        calls.append(cmd[0])
        cmd0 = cmd[0]
        if cmd0 == "mcflirt":
            base = Path(cmd[4])
            base.with_suffix(".nii.gz").touch()
            base.with_suffix(".par").touch()
        elif cmd0 == "fslmaths":
            Path(cmd[-1]).touch()
        elif cmd0 == "flirt":
            Path(cmd[6]).touch()
        if capture and cmd0 == "mcflirt":
            if on_stdout is not None:
                on_stdout("line")
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        stdout = "" if capture else None
        return subprocess.CompletedProcess(cmd, 0, stdout)

    monkeypatch.setattr(fsl, "run_cmd", record)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    assert calls.count("mcflirt") == 2
    assert "flirt" in calls
    assert "fslmaths" in calls


def test_fsl_failure_raises(tmp_path, monkeypatch):
    """Verify FSL failure raises behavior."""
    _make_with_runs(tmp_path)

    def fail(cmd, *, capture=False, on_stdout=None, suppress_final_result_from_live=False):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(fsl, "run_cmd", fail)
    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    with pytest.raises(PePolarError):
        derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())


def test_dir_pairs_lr_rl(tmp_path):
    """Support LR/RL `dir-` pairs by default."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_dir-LR_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_dir-LR_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "i", "TotalReadoutTime": 0.1})
    )

    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-test_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-test_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "i-", "TotalReadoutTime": 0.1})
    )

    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    out = derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    expect = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-RL_epi.nii.gz"
    assert expect in out
    assert expect.exists()


def test_selection_filters_to_missing_ped(tmp_path, monkeypatch):
    """Only runs matching the missing ped are used to build the opposite fmap."""
    _make_dataset(tmp_path)

    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)

    # One run matches the missing ped (j-), one run matches canonical ped (j)
    for run, ped in (("01", "j-"), ("02", "j")):
        bold = func / f"sub-001_ses-01_run-{run}_task-test_bold.nii.gz"
        bold.touch()
        (bold.with_suffix("").with_suffix(".json")).write_text(
            json.dumps({"PhaseEncodingDirection": ped, "TotalReadoutTime": 0.1})
        )

    calls: list[str] = []

    def record(cmd, *, capture=False, on_stdout=None, suppress_final_result_from_live=False):
        calls.append(cmd[0])
        cmd0 = cmd[0]
        if cmd0 == "mcflirt":
            base = Path(cmd[4])
            base.with_suffix(".nii.gz").touch()
            base.with_suffix(".par").touch()
            if capture:
                return subprocess.CompletedProcess(cmd, 0, stdout=MCFLIRT_STDOUT)
        elif cmd0 == "fslmaths":
            Path(cmd[-1]).touch()
        elif cmd0 == "flirt":
            Path(cmd[6]).touch()
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(fsl, "run_cmd", record)

    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())

    # Only one missing-ped run -> only one mcflirt call
    assert calls.count("mcflirt") == 1

    out_json = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_dir-AP_epi.json"
    meta = json.loads(out_json.read_text())
    assert len(meta["IntendedFor"]) == 2


def test_output_preserves_other_entities(tmp_path):
    """If canonical fieldmaps include extra entities (e.g., acq-), keep them."""
    (tmp_path / "dataset_description.json").write_text("{}")
    fmap = tmp_path / "sub-001" / "ses-01" / "fmap"
    fmap.mkdir(parents=True)
    (fmap / "sub-001_ses-01_acq-sefm_dir-PA_epi.nii.gz").touch()
    (fmap / "sub-001_ses-01_acq-sefm_dir-PA_epi.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j", "TotalReadoutTime": 0.1})
    )

    func = tmp_path / "sub-001" / "ses-01" / "func"
    func.mkdir(parents=True)
    (func / "sub-001_ses-01_task-test_bold.nii.gz").touch()
    (func / "sub-001_ses-01_task-test_bold.json").write_text(
        json.dumps({"PhaseEncodingDirection": "j-", "TotalReadoutTime": 0.1})
    )

    ss = [SubjectSession(root=tmp_path, sub="sub-001", ses="ses-01")]
    out = derive_pepolar_fieldmaps(tmp_path, ss, PepolarConfig())
    expect = tmp_path / "sub-001" / "ses-01" / "fmap" / "sub-001_ses-01_acq-sefm_dir-AP_epi.nii.gz"
    assert expect in out
    assert expect.exists()
