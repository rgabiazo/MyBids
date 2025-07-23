import json

from bids_cbrain_runner import __version__
from bids_cbrain_runner.utils.download_utils import maybe_write_dataset_description


def test_runner_generatedby_entry(tmp_path):
    outdir = tmp_path / "out"
    outdir.mkdir()

    cfg = {
        "dataset_descriptions": {
            "cbrain": {
                "demo": {
                    "name": "Demo",
                    # intentionally omit generatedby
                }
            }
        }
    }

    maybe_write_dataset_description(outdir, "demo", cfg)

    with open(outdir / "dataset_description.json", "r", encoding="utf-8") as f:
        dd = json.load(f)

    assert any(
        g.get("Name") == "cbrain_bids_pipeline" and g.get("Version") == __version__
        for g in dd.get("GeneratedBy", [])
    )
