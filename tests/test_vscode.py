from __future__ import annotations

import json
from pathlib import Path

import pytest

from marpme.errors import InvalidConfigError
from marpme.services.vscode import MARP_EXTENSION, VsCodeService, _jsonc_for_parsing


def test_creates_extensions_file(tmp_path: Path) -> None:
    assert VsCodeService().ensure_recommendation(tmp_path)
    content = json.loads((tmp_path / ".vscode/extensions.json").read_text(encoding="utf-8"))
    assert content == {"recommendations": [MARP_EXTENSION]}


def test_merges_and_preserves_jsonc_comments(tmp_path: Path) -> None:
    path = tmp_path / ".vscode/extensions.json"
    path.parent.mkdir()
    path.write_text(
        '{\n  // Keep this comment.\n  "recommendations": [\n'
        '    "some.other-extension", // and this one\n  ],\n'
        '  "unwantedRecommendations": ["legacy.extension"],\n}\n',
        encoding="utf-8",
    )
    assert VsCodeService().ensure_recommendation(tmp_path)
    rendered = path.read_text(encoding="utf-8")
    parsed = json.loads(_jsonc_for_parsing(rendered))
    assert parsed["recommendations"] == ["some.other-extension", MARP_EXTENSION]
    assert parsed["unwantedRecommendations"] == ["legacy.extension"]
    assert "Keep this comment" in rendered
    assert "and this one" in rendered
    assert not VsCodeService().ensure_recommendation(tmp_path)


def test_adds_recommendations_key_to_existing_object(tmp_path: Path) -> None:
    path = tmp_path / ".vscode/extensions.json"
    path.parent.mkdir()
    path.write_text('{\n  "unwantedRecommendations": ["x"]\n}\n', encoding="utf-8")
    VsCodeService().ensure_recommendation(tmp_path)
    parsed = json.loads(_jsonc_for_parsing(path.read_text(encoding="utf-8")))
    assert parsed["recommendations"] == [MARP_EXTENSION]
    assert parsed["unwantedRecommendations"] == ["x"]


def test_adds_recommendations_key_to_empty_strict_json_object(tmp_path: Path) -> None:
    path = tmp_path / ".vscode/extensions.json"
    path.parent.mkdir()
    path.write_text("{}\n", encoding="utf-8")
    VsCodeService().ensure_recommendation(tmp_path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"recommendations": [MARP_EXTENSION]}


def test_invalid_extensions_file_is_not_replaced(tmp_path: Path) -> None:
    path = tmp_path / ".vscode/extensions.json"
    path.parent.mkdir()
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(InvalidConfigError):
        VsCodeService().ensure_recommendation(tmp_path)
    assert path.read_text(encoding="utf-8") == "not json"
