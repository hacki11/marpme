from __future__ import annotations

from pathlib import Path

import yaml

from marpme.errors import (
    CopierFailureError,
    InvalidRepositoryStateError,
    NotInitializedError,
    TemplateUnavailableError,
)
from marpme.models import Repository, TemplateState, UpdateResult


class CopierService:
    """Small compatibility boundary around Copier's public Python API."""

    @staticmethod
    def _answers_file_argument(repository: Repository, *, existing: bool = True) -> Path:
        path = repository.existing_answers_file if existing else repository.answers_file
        return path.relative_to(repository.root)

    def create_repository_environment(
        self,
        repository: Repository,
        source: str,
        *,
        vcs_ref: str | None = None,
    ) -> TemplateState:
        try:
            from copier import run_copy

            run_copy(
                source,
                repository.root,
                vcs_ref=vcs_ref,
                defaults=True,
                quiet=True,
                unsafe=False,
                overwrite=False,
                cleanup_on_error=True,
                answers_file=self._answers_file_argument(repository, existing=False),
            )
        except Exception as exc:
            self._raise_copier_error(exc, source)
        if not repository.answers_file.is_file():
            raise CopierFailureError(
                "The template did not generate .marpme/copier-answers.yml, so future updates "
                "would be unsafe.\n\nAdd the standard Copier answers-file template to the "
                "template repository and retry."
            )
        return self.get_state(repository)

    def update_repository_environment(
        self, repository: Repository, *, vcs_ref: str | None = None
    ) -> UpdateResult:
        before = self.get_state(repository)
        try:
            from copier import run_update

            run_update(
                repository.root,
                vcs_ref=vcs_ref,
                defaults=True,
                quiet=True,
                unsafe=False,
                overwrite=True,
                conflict="inline",
                answers_file=self._answers_file_argument(repository),
            )
        except Exception as exc:
            self._raise_copier_error(exc, before.source or "configured template")
        self.remove_obsolete_answers(repository)
        after = self.get_state(repository)
        return UpdateResult(before.version, after.version)

    def remove_obsolete_answers(self, repository: Repository) -> None:
        """Remove answers from older templates that no longer define a question."""
        path = repository.existing_answers_file
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return
        if not isinstance(raw, dict) or "deck_name" not in raw:
            return
        raw.pop("deck_name")
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    def get_state(self, repository: Repository) -> TemplateState:
        path = repository.existing_answers_file
        if not path.is_file():
            raise NotInitializedError(
                "marpme is not initialized in this repository.\n\n"
                "Create a deck first:\n  marpme new <name>"
            )
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise NotInitializedError(f"Invalid Copier metadata in {path}: {exc}") from exc
        if not isinstance(raw, dict):
            raise NotInitializedError(f"Invalid Copier metadata in {path}.")
        source = raw.get("_src_path")
        commit = raw.get("_commit")
        return TemplateState(
            source=str(source) if source is not None else None,
            version=self._display_version(str(commit)) if commit is not None else None,
            answers=raw,
        )

    @staticmethod
    def _display_version(commit: str) -> str:
        return commit[1:] if commit.startswith("v") else commit

    @staticmethod
    def _raise_copier_error(exc: Exception, source: str) -> None:
        message = str(exc).strip() or exc.__class__.__name__
        lowered = message.lower()
        if "destination repository is dirty" in lowered:
            raise InvalidRepositoryStateError(
                "Copier requires a clean repository before template updates.\n\n"
                "Commit or stash local changes, then retry:\n  marpme update"
            ) from exc
        if any(word in lowered for word in ("clone", "network", "resolve host", "repository")):
            raise TemplateUnavailableError(
                f"Could not access the marpme template at {source}.\n\n"
                "Check your network access and Git credentials, then retry.\n"
                f"Details: {message}"
            ) from exc
        raise CopierFailureError(
            f"Copier template operation failed.\n\nDetails: {message}"
        ) from exc
