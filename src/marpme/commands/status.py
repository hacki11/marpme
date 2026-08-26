from __future__ import annotations

from dataclasses import dataclass

from marpme import __version__
from marpme.services.config import load_config
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


def get_status(*, check_remote: bool = True) -> Status:
    repository = RepositoryService().find()
    config = load_config(repository.config_file)
    state = CopierService().get_state(repository)
    latest = TemplateService().latest_version(state) if check_remote else None
    return Status(__version__, state.version, latest, DeckService().list(repository, config))
