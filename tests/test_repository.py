from pathlib import Path

import pytest

from marpme.errors import InvalidDeckNameError, RepositoryNotFoundError
from marpme.services.repository import RepositoryService


def test_repository_detection_walks_up(repository: Path) -> None:
    nested = repository / "src" / "feature"
    nested.mkdir(parents=True)
    assert RepositoryService().find(nested).root == repository


def test_repository_detection_fails_outside_git() -> None:
    with pytest.raises(RepositoryNotFoundError, match="No Git repository"):
        RepositoryService().find(Path("/"))


@pytest.mark.parametrize("name", ["architecture-review", "Q4.review", "demo_2026", "7"])
def test_valid_deck_names(name: str) -> None:
    assert RepositoryService().validate_deck_name(name) == name


@pytest.mark.parametrize("name", ["", ".", "..", "../../foo", "foo/bar", "has space"])
def test_invalid_deck_names(name: str) -> None:
    with pytest.raises(InvalidDeckNameError):
        RepositoryService().validate_deck_name(name)
