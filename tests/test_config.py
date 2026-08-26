from pathlib import Path

import pytest

from marpme.errors import InvalidConfigError
from marpme.services.config import load_config


def test_config_defaults_when_missing(tmp_path: Path) -> None:
    config = load_config(tmp_path / ".marpme.yml")
    assert config.template_channel == "stable"


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / ".marpme.yml"
    path.write_text("version: 1\ndeck_root: decks\n", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        load_config(path)
