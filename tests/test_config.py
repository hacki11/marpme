from pathlib import Path

import pytest

from marpme.errors import InvalidConfigError
from marpme.services.config import load_config


def test_config_defaults_when_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / ".marpme.yml")
    assert config.presentations_dir == "presentations"
    assert config.template_channel == "stable"


def test_config_parses_custom_presentations_dir(tmp_path: Path) -> None:
    path = tmp_path / ".marpme.yml"
    path.write_text("version: 1\npresentations_dir: docs/slides\n", encoding="utf-8")
    assert load_config(path).presentations_dir == "docs/slides"


def test_config_normalizes_windows_separators(tmp_path: Path) -> None:
    path = tmp_path / ".marpme.yml"
    path.write_text("version: 1\npresentations_dir: docs\\slides\n", encoding="utf-8")
    assert load_config(path).presentations_dir == "docs/slides"


@pytest.mark.parametrize(
    "value",
    [
        "/tmp/decks",
        "../decks",
        "foo/../../bar",
        "C:\\temp\\decks",
        "C:relative-drive-path",
        "\\\\server\\share\\decks",
        "..\\decks",
        "foo\\..\\..\\bar",
    ],
)
def test_config_rejects_paths_outside_repository(tmp_path: Path, value: str) -> None:
    path = tmp_path / ".marpme.yml"
    path.write_text(f"version: 1\npresentations_dir: {value}\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        load_config(path)
