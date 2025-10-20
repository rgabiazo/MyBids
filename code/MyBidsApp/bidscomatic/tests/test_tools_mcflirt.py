from pathlib import Path

from bidscomatic.tools.mcflirt import McflirtConfig, McflirtTool
from bidscomatic.config.tools import load_mcflirt_config


def test_mcflirt_tool_builds(tmp_path):
    """Verify MCFLIRT tool builds behavior."""
    in_file = tmp_path / "in.nii.gz"
    out_dir = tmp_path / "out"
    in_file.touch()
    cfg = McflirtConfig(in_file=in_file, out_dir=out_dir, image="img:latest")
    tool = McflirtTool(cfg)
    spec = tool.build_spec()
    assert spec.image == "img:latest"
    assert spec.volumes[str(in_file.parent)] == "/data:ro"
    assert spec.volumes[str(out_dir)] == "/out"
    assert spec.args[0] == "mcflirt"


def test_load_mcflirt_config(tmp_path):
    """Verify load MCFLIRT config behavior."""
    cfg_dir = tmp_path / "code" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "mcflirt.yaml").write_text(
        "image: testimg\ndefaults:\n  pattern: '*_bold.nii.gz'\n  ref: first\n  width: 123\n  height: 45\n"
    )
    cfg = load_mcflirt_config(tmp_path)
    assert cfg.image == "testimg"
    assert cfg.pattern == "*_bold.nii.gz"
    assert cfg.ref == "first"
    assert cfg.width == 123
    assert cfg.height == 45
