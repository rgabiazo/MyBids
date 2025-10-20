from pathlib import Path

from bidscomatic.utils.naming import slugify, rename_root_if_needed


def test_slugify_lowercase_default():
    """Verify slugify lowercase default behavior."""
    assert slugify("F\xf4\xf4 B\xe4r") == "foo-bar"


def test_slugify_preserve_case():
    """Verify slugify preserve case behavior."""
    assert slugify("F\xf4\xf4 B\xe4r", lowercase=False) == "Foo-Bar"


def test_rename_root_keeps_case(tmp_path: Path):
    """Verify rename root keeps case behavior."""
    src = tmp_path / "Study ABC"
    src.mkdir()
    new_path = rename_root_if_needed(src, "Study ABC")
    assert new_path.name == "Study-ABC"
    assert new_path.exists()
    assert not src.exists()


def test_rename_root_when_target_exists(tmp_path: Path):
    """Verify rename root when target exists behavior."""
    src = tmp_path / "Study ABC"
    target = tmp_path / "Study-ABC"
    src.mkdir()
    target.mkdir()

    returned = rename_root_if_needed(src, "Study ABC")
    assert returned == src
    assert src.exists()
    assert target.exists()
