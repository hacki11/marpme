from __future__ import annotations

from pathlib import Path

import pytest
from conftest import git
from typer.testing import CliRunner

from marpme.cli import app
from marpme.commands.status import get_status
from marpme.commands.update import update_environment
from marpme.services.copier_service import CopierService
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
    assert (in_repository / ".marpme/.marpme.yml").is_file()
    assert not (in_repository / ".copier-answers.yml").exists()
    assert not (in_repository / ".marpme.yml").exists()
    assert (in_repository / ".marpme/theme/company.css").is_file()
    assert (in_repository / ".marpme/skills/slides/SKILL.md").is_file()
    assert (in_repository / "presentations/architecture-review/deck.md").is_file()
    assert "marp-team.marp-vscode" in (in_repository / ".vscode/extensions.json").read_text(
        encoding="utf-8"
    )
    settings = (in_repository / ".vscode/settings.json").read_text(encoding="utf-8")
    assert "./.marpme/theme/company.css" in settings
    assert "./.marpme/theme/company-dark.css" in settings

    second = runner.invoke(app, ["--no-update-check", "new", "customer-demo"])
    assert second.exit_code == 0, second.output
    assert (in_repository / "presentations/customer-demo/deck.md").is_file()
    state = CopierService().get_state(RepositoryService().find(in_repository))
    assert state.answers["deck_name"] == "architecture-review"


def test_legacy_metadata_is_migrated_into_marpme_directory(
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
    (in_repository / ".marpme/copier-answers.yml").replace(in_repository / ".copier-answers.yml")
    (in_repository / ".marpme/.marpme.yml").replace(in_repository / ".marpme.yml")

    second = runner.invoke(app, ["--no-update-check", "new", "second"])

    assert second.exit_code == 0, second.output
    assert (in_repository / ".marpme/copier-answers.yml").is_file()
    assert (in_repository / ".marpme/.marpme.yml").is_file()
    assert not (in_repository / ".copier-answers.yml").exists()
    assert not (in_repository / ".marpme.yml").exists()


def test_existing_deck_is_never_overwritten(in_repository: Path, template_repository: Path) -> None:
    target = in_repository / "presentations/existing"
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
    assert not (in_repository / "presentations/demo").exists()


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

    theme = template_repository / "template/.marpme/theme/company.css"
    theme.write_text("/* template v2 */\n", encoding="utf-8")
    (template_repository / "template/.marpme/scripts").mkdir()
    (template_repository / "template/.marpme/scripts/check.sh").write_text(
        "#!/bin/sh\n", encoding="utf-8"
    )
    git(template_repository, "add", ".")
    git(template_repository, "commit", "-qm", "template v1.1")
    git(template_repository, "tag", "v1.1.0")

    update = update_environment("v1.1.0")
    assert update.previous_version == "1.0.0"
    assert update.current_version == "1.1.0"
    assert theme.read_text(encoding="utf-8") == "/* template v2 */\n"
    assert (in_repository / ".marpme/theme/company.css").read_text(
        encoding="utf-8"
    ) == "/* template v2 */\n"
    assert "Local brand rule." in skill.read_text(encoding="utf-8")
    assert (in_repository / ".marpme/scripts/check.sh").is_file()


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
    managed = in_repository / ".marpme/theme/company.css"
    managed.write_text("/* local theme */\n", encoding="utf-8")
    git(in_repository, "add", ".")
    git(in_repository, "commit", "-qm", "customize theme")

    upstream = template_repository / "template/.marpme/theme/company.css"
    upstream.write_text("/* upstream theme */\n", encoding="utf-8")
    git(template_repository, "add", ".")
    git(template_repository, "commit", "-qm", "change upstream theme")
    git(template_repository, "tag", "v1.1.0")

    update = runner.invoke(app, ["--no-update-check", "update", "--to", "v1.1.0"])
    assert update.exit_code == 1
    assert "completed with conflicts" in update.output
    assert ".marpme/theme/company.css" in update.output
    rendered = managed.read_text(encoding="utf-8")
    assert "<<<<<<<" in rendered and ">>>>>>>" in rendered


def test_shorthand_and_bare_command(
    in_repository: Path, template_repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARPME_TEMPLATE_SOURCE", str(template_repository))
    shorthand = runner.invoke(app, ["--no-update-check", "quick-demo"])
    assert shorthand.exit_code == 0, shorthand.output
    assert (in_repository / "presentations/quick-demo/deck.md").is_file()

    # The group injects the default only when no process-level arguments are present.
    # Invoke a fresh app without global flags to exercise the exact `marpme` behavior.
    bare = runner.invoke(app, [])
    assert bare.exit_code == 0, bare.output
    assert (in_repository / "presentations/slidedeck/deck.md").is_file()


def test_version_option() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.startswith("marpme ")
