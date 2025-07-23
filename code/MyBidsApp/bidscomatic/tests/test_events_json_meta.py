from pathlib import Path
import pandas as pd
from bidscomatic.utils.events_json import build_metadata


def test_build_metadata_levels(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "onset": [0, 1],
            "duration": [0.5, 0.5],
            "stim_file": ["face.png", "house.png"],
            "trial_type": ["face", "house"],
        }
    )
    tsv = tmp_path / "events.tsv"
    df.to_csv(tsv, sep="\t", index=False)

    meta = build_metadata(tsv)
    assert "Levels" not in meta["onset"]
    assert "Levels" not in meta["stim_file"]
    assert meta["trial_type"]["Levels"] == {"face": "", "house": ""}
