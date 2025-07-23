from types import SimpleNamespace
from click.testing import CliRunner

from dicomatic.commands.patients import patients as patients_cmd


def test_list_option_displays_patients(monkeypatch):
    displayed = []

    def fake_fetch(ctx, desc):
        return desc or "dummy", [{"patient_name": "Alice"}, {"patient_name": "Bob"}]

    def fake_display(studies):
        displayed.extend(studies)

    monkeypatch.setattr(
        "dicomatic.commands.patients.fetch_studies_interactive", fake_fetch
    )
    monkeypatch.setattr(
        "dicomatic.commands.patients.display_patients", fake_display
    )
    monkeypatch.setattr(
        "dicomatic.utils.prompts.prompt_for_patient_downloads", lambda ctx, st: None
    )

    runner = CliRunner()
    result = runner.invoke(patients_cmd, ["--list"], obj=SimpleNamespace())
    assert result.exit_code == 0
    assert displayed
