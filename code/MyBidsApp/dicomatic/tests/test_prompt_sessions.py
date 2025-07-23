import sys
from types import ModuleType, SimpleNamespace
sys.modules.setdefault("tableprint", ModuleType("tableprint"))

import click
from dicomatic.utils.prompts import prompt_for_bids_downloads


def test_session_question_and_sessionless(monkeypatch, tmp_path):
    ds = tmp_path / "ds"
    (ds / "sub-01" / "ses-01").mkdir(parents=True)
    (ds / "sub-02").mkdir()
    (ds / "dataset_description.json").write_text("{}")

    grouped = {"sub-001": {"ses-01": [{}]}, "sub-002": {}}

    ctx = click.Context(click.Command("dummy"))
    ctx.obj = SimpleNamespace()

    answers = iter(["y", "y", "n", "ses-01", "n"])
    asked = []

    def fake_prompt(msg, **kwargs):
        asked.append(msg)
        return next(answers)

    monkeypatch.setattr("dicomatic.utils.prompts.prompt_input", fake_prompt)

    invoked = {}

    def fake_invoke(_cmd, **kwargs):
        invoked.update(kwargs)

    monkeypatch.setattr(ctx, "invoke", fake_invoke)

    prompt_for_bids_downloads(ctx, "", grouped)

    assert any("download all sessions" in q for q in asked)
    assert invoked.get("include_sessions") == ["ses-01"]
