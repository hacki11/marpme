from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from marpme.errors import DeckExistsError
from marpme.services.config import template_source
from marpme.services.copier_service import CopierService
from marpme.services.decks import DeckService
from marpme.services.process import ProcessService
from marpme.services.repository import RepositoryService
from marpme.services.template import TemplateService
from marpme.services.vscode import VsCodeService


def create_deck(
    name: str,
    *,
    source: str | None = None,
    vcs_ref: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path, str | None, bool]:
    process = ProcessService()
    repositories = RepositoryService(process)
    copier = CopierService()
    decks = DeckService()
    vscode = VsCodeService()

    report = progress or (lambda _message: None)
    report("Detecting Git repository...")
    repository = repositories.find()
    repositories.validate_deck_name(name)
    process.require_git()
    target = decks.target(repository, name)
    if target.exists():
        raise DeckExistsError(
            f'A deck named "{name}" already exists at '
            f"{target.relative_to(repository.root)}.\n\nNo files were overwritten."
        )

    report("Checking existing VS Code configuration...")
    vscode.validate(repository.root)
    with repositories.mutation_lock(repository):
        repositories.migrate_legacy_metadata(repository)
        initialized = repository.answers_file.is_file()
        if initialized:
            report("Reading installed template state...")
            copier.remove_obsolete_answers(repository)
        if not initialized:
            report("Fetching and applying the presentation template...")
            state = copier.create_repository_environment(
                repository,
                template_source(source),
                vcs_ref=vcs_ref,
            )
        else:
            state = copier.get_state(repository)

        # Templates may create the first deck themselves. Subsequent decks use the
        # The versioned template starter is the only source for new deck content.
        target = decks.target(repository, name)
        report("Creating presentation files...")
        deck_file = target / "deck.md" if target.exists() else decks.create(repository, name)
        vscode_changed = False
        if not initialized:
            report("Loading template VS Code configuration...")
            configuration = TemplateService(process).vscode_configuration(state)
            report("Merging VS Code settings, tasks, and extensions...")
            vscode_changed = vscode.merge_template(repository.root, configuration)
    return deck_file.relative_to(repository.root), state.version, vscode_changed
