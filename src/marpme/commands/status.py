from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from marpme import __version__
from marpme.services.copier_service import CopierService
from marpme.services.decks import DeckService
from marpme.services.repository import RepositoryService
from marpme.services.template import TemplateService


@dataclass(frozen=True)
class Status:
    cli_version: str
    template_version: str | None
    latest_version: str | None
    decks: tuple[str, ...]


def get_status(
    *, check_remote: bool = True, progress: Callable[[str], None] | None = None
) -> Status:
    report = progress or (lambda _message: None)
    report("Detecting Git repository...")
    repository = RepositoryService().find()
    report("Reading installed template state...")
    state = CopierService().get_state(repository)
    if check_remote:
        report("Checking the template repository for newer releases...")
    latest = TemplateService().latest_version(state) if check_remote else None
    report("Finding presentations...")
    decks = DeckService().list(repository)
    return Status(__version__, state.version, latest, decks)
