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
    config = load_config(repository.config_file)
    target = decks.target(repository, config, name)
    if target.exists():
        raise DeckExistsError(
            f'A deck named "{name}" already exists at '
            f"{target.relative_to(repository.root)}.\n\nNo files were overwritten."
        )

    vscode.validate(repository.root)
    initialized = repository.answers_file.is_file()
    with repositories.mutation_lock(repository):
        if not initialized:
            state = copier.create_repository_environment(
                repository,
                template_source(source),
                deck_name=name,
                vcs_ref=vcs_ref,
            )
            if not repository.config_file.exists():
                repository.config_file.write_text(
                    yaml.safe_dump(
                        {
                            "version": 1,
                            "presentations_dir": "presentations",
                            "template": {"channel": "stable"},
                        },
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
            config = load_config(repository.config_file)
        else:
            state = copier.get_state(repository)

        # Templates may create the first deck themselves. Subsequent decks use the
        # versioned .marpme/starter directory, with a safe built-in starter as fallback.
        target = decks.target(repository, config, name)
        if target.exists():
            deck_file = target / "deck.md"
        else:
            deck_file = decks.create(repository, config, name)
        vscode_changed = vscode.ensure_recommendation(repository.root)
    return deck_file.relative_to(repository.root), state.version, vscode_changed
