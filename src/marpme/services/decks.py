from __future__ import annotations

import shutil
from pathlib import Path

from marpme.errors import CopierFailureError, DeckExistsError
from marpme.models import Repository


class DeckService:
    def target(self, repository: Repository, name: str) -> Path:
        return repository.root / name

    def create(self, repository: Repository, name: str) -> Path:
        target = self.target(repository, name)
        if target.exists():
            raise DeckExistsError(
                f'A deck named "{name}" already exists at '
                f"{target.relative_to(repository.root)}.\n\nNo files were overwritten."
            )
        starter = repository.marpme_dir / "starter"
        if not starter.is_dir() or not (starter / "deck.md").is_file():
            raise CopierFailureError(
                "The Marpme template did not provide .marpme/starter/deck.md.\n\n"
                "Use a complete Marpme template release, then retry."
            )
        try:
            shutil.copytree(starter, target)
        except Exception:
            if target.exists():
                shutil.rmtree(target)
            raise
        return target / "deck.md"

    def list(self, repository: Repository) -> tuple[str, ...]:
        return tuple(
            sorted(
                item.name
                for item in repository.root.iterdir()
                if item.is_dir() and (item / "deck.md").is_file()
            )
        )
