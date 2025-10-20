from pathlib import Path
import os
import sys
import types
import numpy as np

from bidscomatic.tools.epi_mask import EpiMaskConfig, EpiMaskTool, MASK_SCRIPT


def test_epi_mask_tool_builds(tmp_path):
    """Verify EPI mask tool builds behavior."""
    cfg = EpiMaskConfig(prep_dir=tmp_path)
    tool = EpiMaskTool(cfg, ["001"], ["taskA"])
    spec = tool.build_spec()
    assert spec.image == cfg.image
    assert str(cfg.prep_dir) in spec.volumes
    assert spec.env.get("SUBJECTS") == "001"
    assert spec.env.get("TASKS") == "taskA"
    assert spec.entrypoint == "python"


def test_mask_fallback(tmp_path, monkeypatch):
    """Verify mask fallback behavior."""
    prep = tmp_path / "sub-001" / "ses-01" / "func"
    prep.mkdir(parents=True)
    bold = prep / "sub-001_ses-01_task-test_space-MNI152NLin6Asym_res-02_desc-preproc_bold.nii.gz"
    bold.write_text("n/a")

    class FakeImg:
        def __init__(self, data):
            self._data = np.array(data)

        def get_fdata(self):
            return self._data

        def to_filename(self, fname):
            Path(fname).write_text("mask")

    def fake_nb_load(_):
        return FakeImg(np.zeros((2, 2, 2)))

    calls: list[tuple[float, int]] = []

    def fake_compute_epi_mask(img, lower_cutoff=0.5, opening=0):
        calls.append((lower_cutoff, opening))
        data = np.zeros((2, 2, 2)) if len(calls) == 1 else np.ones((2, 2, 2))
        return FakeImg(data)

    monkeypatch.setenv("SUBJECTS", "001")
    monkeypatch.setenv("PREP_DIR", str(tmp_path))
    monkeypatch.setitem(sys.modules, "nibabel", types.ModuleType("nibabel"))
    sys.modules["nibabel"].load = fake_nb_load
    monkeypatch.setitem(sys.modules, "nilearn", types.ModuleType("nilearn"))
    nilearn_masking = types.ModuleType("nilearn.masking")
    nilearn_masking.compute_epi_mask = fake_compute_epi_mask
    monkeypatch.setitem(sys.modules, "nilearn.masking", nilearn_masking)

    exec(MASK_SCRIPT, {})

    out = bold.with_name(bold.name.replace("_desc-preproc_bold", "_desc-brain_mask"))
    assert out.exists()
    assert calls == [(0.5, 0), (0.1, 2)]
