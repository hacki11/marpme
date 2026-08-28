from __future__ import annotations

import json
from pathlib import Path

import pytest

from marpme.errors import InvalidConfigError
from marpme.services.vscode import VsCodeService, _jsonc_for_parsing

TEMPLATE_CONFIGURATION = {
    "extensions.json": '{"recommendations": ["marp-team.marp-vscode"]}\n',
    "settings.json": (
        '{"markdown.marp.themes": ["./.marpme/themes/company.css"], '
        '"markdown.marp.html": "all"}\n'
    ),
    "tasks.json": (
        '{"version": "2.0.0", "tasks": '
        '[{"label": "Marp: Preview", "command": "npx"}]}\n'
    ),
}


def test_creates_template_supplied_vscode_files(tmp_path: Path) -> None:
    assert VsCodeService().merge_template(tmp_path, TEMPLATE_CONFIGURATION)

    extensions = json.loads((tmp_path / ".vscode/extensions.json").read_text(encoding="utf-8"))
    settings = json.loads((tmp_path / ".vscode/settings.json").read_text(encoding="utf-8"))
    tasks = json.loads((tmp_path / ".vscode/tasks.json").read_text(encoding="utf-8"))

    assert extensions["recommendations"] == ["marp-team.marp-vscode"]
    assert settings["markdown.marp.themes"] == ["./.marpme/themes/company.css"]
    assert settings["markdown.marp.html"] == "all"
    assert tasks["tasks"][0]["label"] == "Marp: Preview"


def test_merges_all_files_and_preserves_jsonc_comments(tmp_path: Path) -> None:
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    (vscode / "extensions.json").write_text(
        '{\n  // Keep extension comment.\n  "recommendations": [\n'
        '    "some.other-extension", // keep inline comment\n  ],\n}\n',
        encoding="utf-8",
    )
    (vscode / "settings.json").write_text(
        '{\n  // Keep setting comment.\n  "editor.wordWrap": "on",\n'
        '  "markdown.marp.themes": ["./existing.css"],\n}\n',
        encoding="utf-8",
    )
    (vscode / "tasks.json").write_text(
        '{\n  // Keep task comment.\n  "version": "2.0.0",\n'
        '  "tasks": [{"label": "Project: Test", "command": "test"}],\n}\n',
        encoding="utf-8",
    )

    service = VsCodeService()
    assert service.merge_template(tmp_path, TEMPLATE_CONFIGURATION)

    extensions_text = (vscode / "extensions.json").read_text(encoding="utf-8")
    settings_text = (vscode / "settings.json").read_text(encoding="utf-8")
    tasks_text = (vscode / "tasks.json").read_text(encoding="utf-8")
    extensions = json.loads(_jsonc_for_parsing(extensions_text))
    settings = json.loads(_jsonc_for_parsing(settings_text))
    tasks = json.loads(_jsonc_for_parsing(tasks_text))

    assert extensions["recommendations"] == ["some.other-extension", "marp-team.marp-vscode"]
    assert settings["markdown.marp.themes"] == [
        "./existing.css",
        "./.marpme/themes/company.css",
    ]
    assert settings["markdown.marp.html"] == "all"
    assert [task["label"] for task in tasks["tasks"]] == ["Project: Test", "Marp: Preview"]
    assert "Keep extension comment" in extensions_text
    assert "keep inline comment" in extensions_text
    assert "Keep setting comment" in settings_text
    assert "Keep task comment" in tasks_text
    assert not service.merge_template(tmp_path, TEMPLATE_CONFIGURATION)


def test_existing_values_and_same_label_tasks_remain_user_owned(tmp_path: Path) -> None:
    vscode = tmp_path / ".vscode"
    vscode.mkdir()
    (vscode / "settings.json").write_text(
        '{"markdown.marp.html": "none"}\n', encoding="utf-8"
    )
    (vscode / "tasks.json").write_text(
        '{"version": "2.0.0", "tasks": '
        '[{"label": "Marp: Preview", "command": "custom"}]}\n',
        encoding="utf-8",
    )

    VsCodeService().merge_template(tmp_path, TEMPLATE_CONFIGURATION)

    settings = json.loads((vscode / "settings.json").read_text(encoding="utf-8"))
    tasks = json.loads((vscode / "tasks.json").read_text(encoding="utf-8"))
    assert settings["markdown.marp.html"] == "none"
    assert tasks["tasks"] == [{"label": "Marp: Preview", "command": "custom"}]


@pytest.mark.parametrize("filename", ["extensions.json", "settings.json", "tasks.json"])
def test_invalid_target_json_is_not_replaced(tmp_path: Path, filename: str) -> None:
    path = tmp_path / ".vscode" / filename
    path.parent.mkdir()
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(InvalidConfigError, match="not valid JSON or JSONC"):
        VsCodeService().merge_template(tmp_path, TEMPLATE_CONFIGURATION)

    assert path.read_text(encoding="utf-8") == "not json"


def test_invalid_template_json_is_rejected_before_writing(tmp_path: Path) -> None:
    with pytest.raises(InvalidConfigError, match=r"template \.vscode/settings\.json"):
        VsCodeService().merge_template(tmp_path, {"settings.json": "not json"})

    assert not (tmp_path / ".vscode").exists()


def test_update_removes_unchanged_template_settings_and_tasks(tmp_path: Path) -> None:
    service = VsCodeService()
    service.merge_template(tmp_path, TEMPLATE_CONFIGURATION)
    settings_path = tmp_path / ".vscode/settings.json"
    settings_path.write_text(
        settings_path.read_text(encoding="utf-8").replace(
            "{", "{\n  // User comment\n", 1
        ),
        encoding="utf-8",
    )
    updated = {
        "extensions.json": TEMPLATE_CONFIGURATION["extensions.json"],
        "settings.json": (
            '{"markdown.marp.themes": ["./.marpme/themes/company.css"]}\n'
        ),
        "tasks.json": '{"version": "2.0.0", "tasks": []}\n',
    }

    changed, conflicts = service.update_template(tmp_path, updated)

    settings_text = settings_path.read_text(encoding="utf-8")
    settings = json.loads(_jsonc_for_parsing(settings_text))
    tasks = json.loads((tmp_path / ".vscode/tasks.json").read_text(encoding="utf-8"))
    assert changed
    assert conflicts == ()
    assert "markdown.marp.html" not in settings
    assert tasks["tasks"] == []
    assert "User comment" in settings_text


def test_update_reports_conflict_and_preserves_user_changes(tmp_path: Path) -> None:
    service = VsCodeService()
    service.merge_template(tmp_path, TEMPLATE_CONFIGURATION)
    settings_path = tmp_path / ".vscode/settings.json"
    tasks_path = tmp_path / ".vscode/tasks.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["markdown.marp.html"] = "none"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    tasks["tasks"][0]["command"] = "custom"
    tasks_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    updated = {
        **TEMPLATE_CONFIGURATION,
        "settings.json": (
            '{"markdown.marp.themes": ["./.marpme/themes/company.css"], '
            '"markdown.marp.html": "allowed"}\n'
        ),
        "tasks.json": '{"version": "2.0.0", "tasks": []}\n',
    }

    _, conflicts = service.update_template(tmp_path, updated)

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert conflicts == (Path(".vscode/settings.json"), Path(".vscode/tasks.json"))
    assert settings["markdown.marp.html"] == "none"
    assert tasks["tasks"][0]["command"] == "custom"


def test_update_preserves_user_change_when_template_entry_is_unchanged(tmp_path: Path) -> None:
    service = VsCodeService()
    service.merge_template(tmp_path, TEMPLATE_CONFIGURATION)
    settings_path = tmp_path / ".vscode/settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["markdown.marp.html"] = "none"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    changed, conflicts = service.update_template(tmp_path, TEMPLATE_CONFIGURATION)

    assert not changed
    assert conflicts == ()
    assert json.loads(settings_path.read_text(encoding="utf-8"))["markdown.marp.html"] == "none"
