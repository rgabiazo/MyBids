from click.testing import CliRunner
import os
import sys
import types
from pathlib import Path
import numpy as np
import time

from bidscomatic.cli import main as cli_main
from bidscomatic.engines.docker import DockerEngine
from bidscomatic.utils.resources import ResourceSpec
from bidscomatic.config.tools import EpiMaskConfigModel


def test_cli_epi_mask_invokes_engine(tmp_path, monkeypatch):
    """Verify CLI EPI mask invokes engine behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)

    called = {}

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        called["image"] = image
        called["args"] = args
        called["volumes"] = volumes
        called["env"] = env
        called["entrypoint"] = entrypoint
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=1),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "epi-mask",
            "--prep-dir",
            str(prep),
            "--task",
            "test",
            "--runner",
            "docker",
        ],
    )
    assert result.exit_code == 0, result.output
    assert called["volumes"].get(str(prep)) == "/prep"
    assert called["env"].get("SUBJECTS") == "001"
    assert called["env"].get("TASKS") == "test"
    assert called["env"].get("OVERWRITE") == "0"
    assert called["entrypoint"] == "python"


def test_cli_epi_mask_prints_summary(tmp_path, monkeypatch):
    """Verify CLI EPI mask prints summary behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep = tmp_path / "prep"
    (prep / "sub-001").mkdir(parents=True)

    def fake_run(self, image, args, *, volumes, env, entrypoint=None):  # type: ignore[override]
        return 0

    monkeypatch.setattr(DockerEngine, "run", fake_run)
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(
            platform="linux/amd64",
            n_procs=1,
            mem_mb=4096,
            low_mem=True,
            omp_threads=1,
            cpu_docker=2,
            mem_total_mb=8192,
            headroom_mb=4096,
            host_arch="arm64",
            mode="docker",
        ),
    )
    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.load_epi_mask_config",
        lambda root, overrides=None: EpiMaskConfigModel(
            image="other/image:1.0",
            prep_dir=prep,
            low_mem=False,
            n_procs=1,
            mem_mb=4000,
            omp_threads=1,
            overwrite=False,
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "epi-mask",
            "--prep-dir",
            str(prep),
            "--runner",
            "docker",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Inside-VM: CPUs=2, MemTotal=8192MB" in result.output


def test_cli_epi_mask_creates_mask(tmp_path, monkeypatch):
    """Verify CLI EPI mask creates mask behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep_dir = tmp_path / "prep"
    func = prep_dir / "sub-005" / "ses-01" / "func"
    func.mkdir(parents=True)
    bold = func / (
        "sub-005_ses-01_task-test_space-MNI152NLin6Asym_"
        "res-02_desc-preproc_bold.nii.gz"
    )
    other = func / (
        "sub-005_ses-01_task-other_space-MNI152NLin6Asym_"
        "res-02_desc-preproc_bold.nii.gz"
    )
    t1w = func / (
        "sub-005_ses-01_task-test_space-T1w_desc-preproc_bold.nii.gz"
    )
    bold.write_text("n/a")
    other.write_text("n/a")
    t1w.write_text("n/a")

    class FakeImg:
        def __init__(self, data):
            self._data = np.array(data)

        def get_fdata(self):
            return self._data

        def to_filename(self, fname):
            Path(fname).write_text("mask")

    def fake_nb_load(_):
        return FakeImg(np.ones((2, 2, 2)))

    def fake_compute_epi_mask(img, lower_cutoff=0.5, opening=0):
        return FakeImg(np.ones((2, 2, 2)))

    monkeypatch.setitem(sys.modules, "nibabel", types.ModuleType("nibabel"))
    sys.modules["nibabel"].load = fake_nb_load
    monkeypatch.setitem(sys.modules, "nilearn", types.ModuleType("nilearn"))
    nilearn_masking = types.ModuleType("nilearn.masking")
    nilearn_masking.compute_epi_mask = fake_compute_epi_mask
    monkeypatch.setitem(sys.modules, "nilearn.masking", nilearn_masking)

    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(
            platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=1
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "epi-mask",
            "--prep-dir",
            str(prep_dir),
            "--subjects",
            "005",
            "--task",
            "test",
        ],
    )
    assert result.exit_code == 0, result.output
    mask = bold.with_name(bold.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
    assert mask.exists()
    other_mask = other.with_name(other.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
    assert not other_mask.exists()
    t1w_mask = t1w.with_name(t1w.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
    assert not t1w_mask.exists()


def test_cli_epi_mask_creates_mask_no_session(tmp_path, monkeypatch):
    """Verify CLI EPI mask creates mask NO session behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep_dir = tmp_path / "prep"
    func = prep_dir / "sub-006" / "func"
    func.mkdir(parents=True)
    bold = func / (
        "sub-006_task-test_space-MNI152NLin6Asym_res-2_desc-preproc_bold.nii.gz"
    )
    bold.write_text("n/a")

    class FakeImg:
        def __init__(self, data):
            self._data = np.array(data)

        def get_fdata(self):
            return self._data

        def to_filename(self, fname):
            Path(fname).write_text("mask")

    def fake_nb_load(_):
        return FakeImg(np.ones((2, 2, 2)))

    def fake_compute_epi_mask(img, lower_cutoff=0.5, opening=0):
        return FakeImg(np.ones((2, 2, 2)))

    monkeypatch.setitem(sys.modules, "nibabel", types.ModuleType("nibabel"))
    sys.modules["nibabel"].load = fake_nb_load
    monkeypatch.setitem(sys.modules, "nilearn", types.ModuleType("nilearn"))
    nilearn_masking = types.ModuleType("nilearn.masking")
    nilearn_masking.compute_epi_mask = fake_compute_epi_mask
    monkeypatch.setitem(sys.modules, "nilearn.masking", nilearn_masking)

    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(
            platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=1
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "--bids-root",
            str(tmp_path),
            "preprocess",
            "epi-mask",
            "--prep-dir",
            str(prep_dir),
            "--subjects",
            "006",
        ],
    )
    assert result.exit_code == 0, result.output
    mask = bold.with_name(bold.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
    assert mask.exists()


def test_cli_epi_mask_overwrite(tmp_path, monkeypatch):
    """Verify CLI EPI mask overwrite behavior."""
    (tmp_path / "dataset_description.json").write_text("{}")
    prep_dir = tmp_path / "prep"
    func = prep_dir / "sub-007" / "ses-01" / "func"
    func.mkdir(parents=True)
    bold = func / (
        "sub-007_ses-01_task-test_space-MNI152NLin6Asym_res-02_desc-preproc_bold.nii.gz"
    )
    bold.write_text("n/a")

    class FakeImg:
        def __init__(self, data):
            self._data = np.array(data)

        def get_fdata(self):
            return self._data

        def to_filename(self, fname):
            Path(fname).write_text("mask")

    def fake_nb_load(_):
        return FakeImg(np.ones((2, 2, 2)))

    def fake_compute_epi_mask(img, lower_cutoff=0.5, opening=0):
        return FakeImg(np.ones((2, 2, 2)))

    monkeypatch.setitem(sys.modules, "nibabel", types.ModuleType("nibabel"))
    sys.modules["nibabel"].load = fake_nb_load
    monkeypatch.setitem(sys.modules, "nilearn", types.ModuleType("nilearn"))
    nilearn_masking = types.ModuleType("nilearn.masking")
    nilearn_masking.compute_epi_mask = fake_compute_epi_mask
    monkeypatch.setitem(sys.modules, "nilearn.masking", nilearn_masking)

    monkeypatch.setattr(
        "bidscomatic.cli.preprocess.tune_resources",
        lambda *a, **k: ResourceSpec(
            platform=None, n_procs=1, mem_mb=1000, low_mem=False, omp_threads=1
        ),
    )

    runner = CliRunner()
    cmd = [
        "--bids-root",
        str(tmp_path),
        "preprocess",
        "epi-mask",
        "--prep-dir",
        str(prep_dir),
        "--subjects",
        "007",
        "--task",
        "test",
    ]
    result1 = runner.invoke(cli_main, cmd)
    assert result1.exit_code == 0, result1.output
    mask = bold.with_name(bold.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
    assert mask.exists()
    mtime1 = mask.stat().st_mtime
    time.sleep(1)
    result2 = runner.invoke(cli_main, cmd)
    assert result2.exit_code == 0, result2.output
    assert mask.stat().st_mtime == mtime1
    time.sleep(1)
    result3 = runner.invoke(cli_main, cmd + ["--overwrite"])
    assert result3.exit_code == 0, result3.output
    assert mask.stat().st_mtime > mtime1
