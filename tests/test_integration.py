from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import git
from typer.testing import CliRunner

from marpme.cli import app
from marpme.commands.status import get_status
from marpme.commands.update import update_environment
from marpme.errors import CopierFailureError
from marpme.models import Repository
from marpme.services.copier_service import CopierService
from marpme.services.decks import DeckService
from marpme.services.repository import RepositoryService

runner = CliRunner()


def test_new_initializes_environment_and_multiple_decks(
    in_repository: Path, template_repository: Path
) -> None:
    first = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "architecture-review",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert first.exit_code == 0, first.output
    assert (in_repository / ".marpme/copier-answers.yml").is_file()
    assert not (in_repository / ".copier-answers.yml").exists()
    assert (in_repository / ".marpme/themes/company.css").is_file()
    assert (in_repository / ".marpme/skills/slides/SKILL.md").is_file()
    assert (in_repository / "architecture-review/deck.md").is_file()
    assert "marp-team.marp-vscode" in (in_repository / ".vscode/extensions.json").read_text(
        encoding="utf-8"
    )
    settings = (in_repository / ".vscode/settings.json").read_text(encoding="utf-8")
    assert "./.marpme/themes/company.css" in settings
    assert (in_repository / ".vscode/tasks.json").is_file()

    second = runner.invoke(app, ["--no-update-check", "new", "customer-demo"])
    assert second.exit_code == 0, second.output
    assert (in_repository / "customer-demo/deck.md").is_file()
    state = CopierService().get_state(RepositoryService().find(in_repository))
    assert "deck_name" not in state.answers


def test_legacy_copier_metadata_is_migrated_into_marpme_directory(
    in_repository: Path, template_repository: Path
) -> None:
    created = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "first",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert created.exit_code == 0, created.output
    answers = in_repository / ".marpme/copier-answers.yml"
    answers.write_text(answers.read_text(encoding="utf-8") + "deck_name: first\n", encoding="utf-8")
    answers.replace(in_repository / ".copier-answers.yml")

    second = runner.invoke(app, ["--no-update-check", "new", "second"])

    assert second.exit_code == 0, second.output
    assert (in_repository / ".marpme/copier-answers.yml").is_file()
    assert not (in_repository / ".copier-answers.yml").exists()
    state = CopierService().get_state(RepositoryService().find(in_repository))
    assert "deck_name" not in state.answers


def test_existing_deck_is_never_overwritten(in_repository: Path, template_repository: Path) -> None:
    target = in_repository / "existing"
    target.mkdir(parents=True)
    original = target / "deck.md"
    original.write_text("valuable content\n", encoding="utf-8")
    result = runner.invoke(
        app,
        ["--no-update-check", "new", "existing", "--template", str(template_repository)],
    )
    assert result.exit_code == 1
    assert "No files were overwritten" in result.output
    assert original.read_text(encoding="utf-8") == "valuable content\n"
    assert not (in_repository / ".marpme/copier-answers.yml").exists()


def test_deck_creation_requires_template_starter(in_repository: Path) -> None:
    (in_repository / ".marpme").mkdir()

    with pytest.raises(CopierFailureError, match=r"starter/deck\.md"):
        DeckService().create(Repository(in_repository), "demo")

    assert not (in_repository / "demo").exists()


def test_invalid_vscode_json_fails_before_template_mutation(
    in_repository: Path, template_repository: Path
) -> None:
    vscode = in_repository / ".vscode/extensions.json"
    vscode.parent.mkdir()
    vscode.write_text("invalid json", encoding="utf-8")
    result = runner.invoke(
        app,
        ["--no-update-check", "new", "demo", "--template", str(template_repository)],
    )
    assert result.exit_code == 1
    assert "not valid JSON" in result.output
    assert "JSONC" in result.output
    assert not (in_repository / ".marpme/copier-answers.yml").exists()
    assert not (in_repository / "demo").exists()


def test_copier_update_applies_new_tag_and_preserves_local_changes(
    in_repository: Path, template_repository: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "demo",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert result.exit_code == 0, result.output
    skill = in_repository / ".marpme/skills/slides/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nLocal brand rule.\n", encoding="utf-8")
    git(in_repository, "add", ".")
    git(in_repository, "commit", "-qm", "add deck and local brand rule")

    theme = template_repository / "template/.marpme/themes/company.css"
    theme.write_text("/* template v2 */\n", encoding="utf-8")
    (template_repository / "template/.marpme/scripts").mkdir()
    (template_repository / "template/.marpme/scripts/check.sh").write_text(
        "#!/bin/sh\n", encoding="utf-8"
    )
    (template_repository / ".vscode/settings.json").write_text(
        '{"markdown.marp.themes": ["./.marpme/themes/company.css"], '
        '"markdown.marp.outlineExtension": false}\n',
        encoding="utf-8",
    )
    (template_repository / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.1.0 - 2026-08-26\n\n- Updated company theme.\n\n"
        "## 1.0.0 - 2026-08-26\n\n- Initial template.\n",
        encoding="utf-8",
    )
    git(template_repository, "add", ".")
    git(template_repository, "commit", "-qm", "template v1.1")
    git(template_repository, "tag", "v1.1.0")

    update = update_environment("v1.1.0")
    assert update.previous_version == "1.0.0"
    assert update.current_version == "1.1.0"
    assert theme.read_text(encoding="utf-8") == "/* template v2 */\n"
    assert (in_repository / ".marpme/themes/company.css").read_text(
        encoding="utf-8"
    ) == "/* template v2 */\n"
    assert "Local brand rule." in skill.read_text(encoding="utf-8")
    assert (in_repository / ".marpme/scripts/check.sh").is_file()
    settings = (in_repository / ".vscode/settings.json").read_text(encoding="utf-8")
    assert '"markdown.marp.outlineExtension": false' in settings
    assert update.changes == ("Updated company theme.",)


def test_update_displays_changelog_changes(in_repository: Path, template_repository: Path) -> None:
    created = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "demo",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert created.exit_code == 0, created.output
    git(in_repository, "add", ".")
    git(in_repository, "commit", "-qm", "create deck")
    (template_repository / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.1.0 - 2026-08-26\n\n- Added diagram primitives.\n\n"
        "## 1.0.0 - 2026-08-26\n\n- Initial template.\n",
        encoding="utf-8",
    )
    git(template_repository, "add", ".")
    git(template_repository, "commit", "-qm", "add release notes")
    git(template_repository, "tag", "v1.1.0")

    updated = runner.invoke(app, ["--no-update-check", "update", "--to", "v1.1.0"])

    assert updated.exit_code == 0, updated.output
    assert "Changes:" in updated.output
    assert "Added diagram primitives." in updated.output


def test_update_reports_vscode_conflict_and_preserves_user_task(
    in_repository: Path, template_repository: Path
) -> None:
    created = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "demo",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert created.exit_code == 0, created.output
    target_tasks = in_repository / ".vscode/tasks.json"
    target = json.loads(target_tasks.read_text(encoding="utf-8"))
    target["tasks"][0]["command"] = "custom-preview"
    target_tasks.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    git(in_repository, "add", ".")
    git(in_repository, "commit", "-qm", "customize preview task")

    source_tasks = template_repository / ".vscode/tasks.json"
    source = json.loads(source_tasks.read_text(encoding="utf-8"))
    source["tasks"][0]["command"] = "upstream-preview"
    source_tasks.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    git(template_repository, "add", ".")
    git(template_repository, "commit", "-qm", "change preview task")
    git(template_repository, "tag", "v1.1.0")

    updated = runner.invoke(app, ["--no-update-check", "update", "--to", "v1.1.0"])

    assert updated.exit_code == 1
    assert "VS Code configuration has conflicts" in updated.output
    assert ".vscode/tasks.json" in updated.output
    rendered = json.loads(target_tasks.read_text(encoding="utf-8"))
    assert rendered["tasks"][0]["command"] == "custom-preview"


def test_status_works_offline(in_repository: Path, template_repository: Path) -> None:
    created = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "demo",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert created.exit_code == 0, created.output
    (in_repository / "src").mkdir()
    status = get_status(check_remote=False)
    assert status.template_version == "1.0.0"
    assert status.latest_version is None
    assert status.decks == ("demo",)
    rendered = runner.invoke(app, ["--no-update-check", "status", "--offline"])
    assert rendered.exit_code == 0
    assert "unknown (offline or unavailable)" in rendered.output


def test_copier_conflicts_are_reported(in_repository: Path, template_repository: Path) -> None:
    created = runner.invoke(
        app,
        [
            "--no-update-check",
            "new",
            "demo",
            "--template",
            str(template_repository),
            "--template-ref",
            "v1.0.0",
        ],
    )
    assert created.exit_code == 0, created.output
    managed = in_repository / ".marpme/themes/company.css"
    managed.write_text("/* local theme */\n", encoding="utf-8")
    git(in_repository, "add", ".")
    git(in_repository, "commit", "-qm", "customize theme")

    upstream = template_repository / "template/.marpme/themes/company.css"
    upstream.write_text("/* upstream theme */\n", encoding="utf-8")
    git(template_repository, "add", ".")
    git(template_repository, "commit", "-qm", "change upstream theme")
    git(template_repository, "tag", "v1.1.0")

    update = runner.invoke(app, ["--no-update-check", "update", "--to", "v1.1.0"])
    assert update.exit_code == 1
    assert "completed with conflicts" in update.output
    assert ".marpme/themes/company.css" in update.output
    rendered = managed.read_text(encoding="utf-8")
    assert "<<<<<<<" in rendered and ">>>>>>>" in rendered


def test_shorthand_and_bare_command(
    in_repository: Path, template_repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARPME_TEMPLATE_SOURCE", str(template_repository))
    shorthand = runner.invoke(app, ["--no-update-check", "quick-demo"])
    assert shorthand.exit_code == 0, shorthand.output
    assert (in_repository / "quick-demo/deck.md").is_file()

    # The group injects the default only when no process-level arguments are present.
    # Invoke a fresh app without global flags to exercise the exact `marpme` behavior.
    bare = runner.invoke(app, [])
    assert bare.exit_code == 0, bare.output
    assert (in_repository / "slidedeck/deck.md").is_file()


def test_version_option() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("marpme ")
