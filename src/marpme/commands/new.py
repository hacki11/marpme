from __future__ import annotations

from pathlib import Path

import yaml

from marpme.errors import DeckExistsError
from marpme.services.config import load_config, template_source
from marpme.services.copier_service import CopierService
from marpme.services.decks import DeckService
from marpme.services.process import ProcessService
from marpme.services.repository import RepositoryService
from marpme.services.vscode import VsCodeService


def create_deck(
    name: str, *, source: str | None = None, vcs_ref: str | None = None
) -> tuple[Path, str | None, bool]:
    process = ProcessService()
    repositories = RepositoryService(process)
    copier = CopierService()
    decks = DeckService()
    vscode = VsCodeService()

    repository = repositories.find()
    repositories.validate_deck_name(name)
    process.require_git()
    load_config(repository.existing_config_file)
    target = decks.target(repository, name)
    if target.exists():
        raise DeckExistsError(
            f'A deck named "{name}" already exists at '
            f"{target.relative_to(repository.root)}.\n\nNo files were overwritten."
        )

    vscode.validate(repository.root)
    vscode.validate_settings(repository.root)
    with repositories.mutation_lock(repository):
        repositories.migrate_legacy_metadata(repository)
        initialized = repository.answers_file.is_file()
        if not initialized:
            state = copier.create_repository_environment(
                repository,
                template_source(source),
                deck_name=name,
                vcs_ref=vcs_ref,
            )
            if not repository.config_file.exists():
                repository.marpme_dir.mkdir(parents=True, exist_ok=True)
                repository.config_file.write_text(
                    yaml.safe_dump(
                        {
                            "version": 1,
                            "template": {"channel": "stable"},
                        },
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
            load_config(repository.existing_config_file)
        else:
            state = copier.get_state(repository)

        # Templates may create the first deck themselves. Subsequent decks use the
        # The versioned template starter is the only source for new deck content.
        target = decks.target(repository, name)
        deck_file = target / "deck.md" if target.exists() else decks.create(repository, name)
        vscode_changed = vscode.ensure_recommendation(repository.root)
        vscode.ensure_theme_settings(repository.root)
    return deck_file.relative_to(repository.root), state.version, vscode_changed
