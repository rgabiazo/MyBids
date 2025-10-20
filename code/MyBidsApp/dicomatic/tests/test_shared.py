import sys
from types import ModuleType, SimpleNamespace

import click

# ``dicomatic.utils.prompts`` depends on ``tableprint`` which may not be
# installed in the test environment.  Provide a no-op stub so imports succeed.
sys.modules.setdefault("tableprint", ModuleType("tableprint"))

from dicomatic.commands import _shared


def _make_sentinel(name: str = "UNSET"):
    sentinel_cls = type(
        "Sentinel",
        (),
        {
            "__init__": lambda self, value=name: setattr(self, "name", value),
            "__str__": lambda self: f"Sentinel.{self.name}",
        },
    )
    return sentinel_cls()


def test_fetch_studies_interactive_ignores_click_sentinel(monkeypatch):
    ctx = click.Context(click.Command("dummy"))
    ctx.obj = SimpleNamespace()

    calls = []

    def fake_fetch(_ctx, description):
        calls.append(description)
        return [{"study_uid": "1"}] if description == "valid" else []

    sentinel = _make_sentinel()

    answers = iter(["valid"])

    monkeypatch.setattr(_shared, "fetch_studies", fake_fetch)
    monkeypatch.setattr(
        "dicomatic.commands._shared.prompt_input",
        lambda _msg: next(answers),
    )

    desc, studies = _shared.fetch_studies_interactive(ctx, sentinel)

    assert desc == "valid"
    assert studies == [{"study_uid": "1"}]
    assert calls == ["valid"]
