from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from marpme.errors import GitMissingError, InvalidRepositoryStateError


class ProcessService:
    def has_git(self) -> bool:
        return shutil.which("git") is not None

    def require_git(self) -> None:
        if not self.has_git():
            raise GitMissingError(
                "Git is required for marpme template operations.\n\n"
                "Install Git and retry:\n  https://git-scm.com/"
            )

    def run_git(
        self, args: list[str], cwd: Path, *, check: bool = True, timeout: float = 30
    ) -> subprocess.CompletedProcess[str]:
        self.require_git()
        try:
            return subprocess.run(
                ["git", *args],
                cwd=cwd,
                check=check,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise InvalidRepositoryStateError("Git operation timed out.") from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "Git operation failed.").strip()
            raise InvalidRepositoryStateError(detail) from exc
