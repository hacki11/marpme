from __future__ import annotations

import shutil
from pathlib import Path

from marpme.errors import DeckExistsError
from marpme.models import Repository

DEFAULT_DECK = """---
marp: true
theme: company
paginate: true
---

# {title}

---

## Next slide

Start writing your presentation here.
"""


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
        target.parent.mkdir(parents=True, exist_ok=True)
        starter = repository.marpme_dir / "starter"
        try:
            if starter.is_dir():
                shutil.copytree(starter, target)
            else:
                target.mkdir()
                (target / "assets").mkdir()
                (target / "deck.md").write_text(
                    DEFAULT_DECK.format(title=name.replace("-", " ").replace("_", " ").title()),
                    encoding="utf-8",
                )
                (target / "custom.css").write_text(
                    "/* Presentation-specific styles. */\n", encoding="utf-8"
                )
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
