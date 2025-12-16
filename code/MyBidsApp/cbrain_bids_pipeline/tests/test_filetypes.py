from bids_cbrain_runner.utils.filetypes import guess_filetype


def test_guess_filetype_fsl_design():
    cfg = {
        "filetype_inference": {
            "fallback": "BidsSubject",
            "patterns": {
                "*.fsf": "FslDesignFile",
            },
        }
    }

    assert guess_filetype("design.fsf", cfg) == "FslDesignFile"
