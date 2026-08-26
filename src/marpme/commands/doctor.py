from __future__ import annotations

from marpme.models import DoctorCheck
from marpme.services.copier_service import CopierService
from marpme.services.process import ProcessService
from marpme.services.repository import RepositoryService
from marpme.services.template import TemplateService
from marpme.services.vscode import VsCodeService


def run_doctor(*, check_remote: bool = True) -> tuple[DoctorCheck, ...]:
    process = ProcessService()
    repositories = RepositoryService(process)
    checks: list[DoctorCheck] = []
    has_git = process.has_git()
    checks.append(
        DoctorCheck("Git", has_git, "" if has_git else "Install Git from https://git-scm.com/")
    )
    try:
        repository = repositories.find()
    except Exception as exc:
        checks.append(DoctorCheck("Repository", False, str(exc).splitlines()[0]))
        return tuple(checks)
    checks.append(DoctorCheck("Repository", True, str(repository.root)))
    try:
        state = CopierService().get_state(repository)
        checks.append(DoctorCheck("Marpme metadata", True, state.version or "version not recorded"))
    except Exception as exc:
        checks.append(DoctorCheck("Marpme metadata", False, str(exc).splitlines()[0]))
        state = None
    vscode_ok = VsCodeService().is_integrated(repository.root)
    checks.append(
        DoctorCheck(
            "VS Code recommendation",
            vscode_ok,
            "" if vscode_ok else "Run marpme new <name> to repair it.",
        )
    )
    themes_ok = VsCodeService().themes_are_integrated(repository.root)
    checks.append(
        DoctorCheck(
            "VS Code themes",
            themes_ok,
            "" if themes_ok else "Run marpme new <name> to repair them.",
        )
    )
    if check_remote and state is not None:
        latest = TemplateService(process).latest_version(state)
        checks.append(
            DoctorCheck(
                "Template source reachable",
                latest is not None,
                latest or "Could not query stable template tags.",
            )
        )
    return tuple(checks)
