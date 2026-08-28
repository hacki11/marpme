from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from marpme.errors import (
    InvalidDeckNameError,
    InvalidRepositoryStateError,
    RepositoryNotFoundError,
)
from marpme.models import Repository
from marpme.services.process import ProcessService

DECK_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class RepositoryService:
    def __init__(self, process: ProcessService | None = None) -> None:
        self.process = process or ProcessService()

    def find(self, start: Path | None = None) -> Repository:
        current = (start or Path.cwd()).resolve()
        if current.is_file():
            current = current.parent
        for candidate in (current, *current.parents):
            if (candidate / ".git").exists():
                return Repository(candidate)
        raise RepositoryNotFoundError(
            "No Git repository found.\n\nRun marpme from inside a repository."
        )

    def validate_deck_name(self, name: str) -> str:
        if not DECK_NAME_PATTERN.fullmatch(name) or name in {".", ".."}:
            raise InvalidDeckNameError(
                f'Invalid deck name "{name}".\n\n'
                "Use letters, numbers, dots, underscores, or hyphens; paths are not allowed."
            )
        return name

    def migrate_legacy_metadata(self, repository: Repository) -> None:
        """Move pre-.marpme metadata into the current managed directory."""
        moves = (
            (repository.legacy_answers_file, repository.answers_file),
        )
        pending = [(source, destination) for source, destination in moves if source.is_file()]
        if not pending:
            return
        repository.marpme_dir.mkdir(parents=True, exist_ok=True)
        for source, destination in pending:
            if not destination.exists():
                source.replace(destination)

    def unresolved_conflicts(self, repository: Repository) -> tuple[Path, ...]:
        result = self.process.run_git(["diff", "--name-only", "--diff-filter=U"], repository.root)
        return tuple(Path(line) for line in result.stdout.splitlines() if line.strip())

    def copier_conflicts(self, repository: Repository) -> tuple[Path, ...]:
        """Find Copier's inline merge markers among files changed by an update."""
        result = self.process.run_git(["diff", "--name-only"], repository.root)
        conflicts: list[Path] = list(self.unresolved_conflicts(repository))
        for line in result.stdout.splitlines():
            relative = Path(line)
            candidate = (repository.root / relative).resolve()
            try:
                candidate.relative_to(repository.root)
                content = candidate.read_text(encoding="utf-8")
            except (OSError, UnicodeError, ValueError):
                continue
            lines = content.splitlines()
            has_start = any(item.startswith("<<<<<<< ") for item in lines)
            has_middle = any(item == "=======" for item in lines)
            has_end = any(item.startswith(">>>>>>> ") for item in lines)
            if has_start and has_middle and has_end and relative not in conflicts:
                conflicts.append(relative)
        return tuple(conflicts)

    def require_no_conflicts(self, repository: Repository) -> None:
        conflicts = self.unresolved_conflicts(repository)
        if conflicts:
            shown = "\n".join(f"  {path}" for path in conflicts)
            raise InvalidRepositoryStateError(
                "The repository has unresolved Git conflicts.\n\n"
                f"Resolve them before updating marpme:\n{shown}"
            )

    @contextmanager
    def mutation_lock(self, repository: Repository) -> Iterator[None]:
        # Keep the advisory lock under Git's private directory. Copier requires a
        # clean worktree before updates, so a visible `.marpme/.lock` would make
        # the very operation it guards fail its safety check.
        git_path = self.process.run_git(
            ["rev-parse", "--git-path", "marpme.lock"], repository.root
        ).stdout.strip()
        lock_path = Path(git_path)
        if not lock_path.is_absolute():
            lock_path = repository.root / lock_path
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"pid: {os.getpid()}\ncreated: {int(time.time())}\n"
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if self._remove_stale_lock(lock_path):
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            else:
                raise InvalidRepositoryStateError(
                    f"Another marpme operation is using this repository ({lock_path})."
                ) from None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    @staticmethod
    def _remove_stale_lock(lock_path: Path) -> bool:
        try:
            content = lock_path.read_text(encoding="utf-8")
            pid_line = next(line for line in content.splitlines() if line.startswith("pid:"))
            pid = int(pid_line.partition(":")[2].strip())
            os.kill(pid, 0)
        except ProcessLookupError:
            lock_path.unlink(missing_ok=True)
            return True
        except (OSError, StopIteration, ValueError):
            try:
                age = time.time() - lock_path.stat().st_mtime
            except OSError:
                return False
            if age > 60 * 60:
                lock_path.unlink(missing_ok=True)
                return True
        return False
