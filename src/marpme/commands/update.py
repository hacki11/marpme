from __future__ import annotations

from marpme.models import UpdateResult
from marpme.services.copier_service import CopierService
from marpme.services.process import ProcessService
from marpme.services.repository import RepositoryService
from marpme.services.template import TemplateService
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
    with repositories.mutation_lock(repository):
        result = copier.update_repository_environment(
            repository, vcs_ref=None if vcs_ref == "latest" else vcs_ref
        )
        state = copier.get_state(repository)
        configuration = TemplateService(process).vscode_configuration(state)
        _, configuration_conflicts = vscode.update_template(repository.root, configuration)
        conflicts = repositories.copier_conflicts(repository)
    state = copier.get_state(repository)
    changes = TemplateService(process).changelog_changes(state)
    return UpdateResult(
        previous_version=result.previous_version,
        current_version=result.current_version,
        conflicts=conflicts,
        changes=changes,
        configuration_conflicts=configuration_conflicts,
    )
