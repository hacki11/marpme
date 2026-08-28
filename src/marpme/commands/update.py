from __future__ import annotations

from collections.abc import Callable

from marpme.models import UpdateResult
from marpme.services.copier_service import CopierService
from marpme.services.process import ProcessService
from marpme.services.repository import RepositoryService
from marpme.services.template import TemplateService
from marpme.services.vscode import VsCodeService


def update_environment(
    vcs_ref: str | None = None, *, progress: Callable[[str], None] | None = None
) -> UpdateResult:
    report = progress or (lambda _message: None)
    process = ProcessService()
    repositories = RepositoryService(process)
    report("Detecting Git repository...")
    repository = repositories.find()
    process.require_git()
    report("Checking repository and template state...")
    repositories.require_no_conflicts(repository)
    copier = CopierService()
    copier.get_state(repository)
    vscode = VsCodeService()
    vscode.validate(repository.root)
    with repositories.mutation_lock(repository):
        report("Fetching and applying the template update...")
        result = copier.update_repository_environment(
            repository, vcs_ref=None if vcs_ref == "latest" else vcs_ref
        )
        state = copier.get_state(repository)
        report("Loading template VS Code configuration...")
        configuration = TemplateService(process).vscode_configuration(state)
        report("Merging VS Code settings, tasks, and extensions...")
        _, configuration_conflicts = vscode.update_template(repository.root, configuration)
        report("Checking for merge conflicts...")
        conflicts = repositories.copier_conflicts(repository)
    state = copier.get_state(repository)
    report("Reading template changelog...")
    changes = TemplateService(process).changelog_changes(state)
    return UpdateResult(
        previous_version=result.previous_version,
        current_version=result.current_version,
        conflicts=conflicts,
        changes=changes,
        configuration_conflicts=configuration_conflicts,
    )
