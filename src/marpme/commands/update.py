from __future__ import annotations

from marpme.models import UpdateResult
from marpme.services.copier_service import CopierService
from marpme.services.process import ProcessService
from marpme.services.repository import RepositoryService
from marpme.services.vscode import VsCodeService


def update_environment(vcs_ref: str | None = None) -> UpdateResult:
    process = ProcessService()
    repositories = RepositoryService(process)
    repository = repositories.find()
    process.require_git()
    repositories.require_no_conflicts(repository)
    copier = CopierService()
    copier.get_state(repository)
    vscode = VsCodeService()
    vscode.validate(repository.root)
    vscode.validate_settings(repository.root)
    with repositories.mutation_lock(repository):
        result = copier.update_repository_environment(
            repository, vcs_ref=None if vcs_ref == "latest" else vcs_ref
        )
        vscode.ensure_recommendation(repository.root)
        vscode.ensure_theme_settings(repository.root)
        conflicts = repositories.copier_conflicts(repository)
    return UpdateResult(result.previous_version, result.current_version, conflicts)
