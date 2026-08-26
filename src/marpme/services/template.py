from __future__ import annotations

import re
import tempfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

from marpme.models import TemplateState
from marpme.services.process import ProcessService

TAG_PATTERN = re.compile(r"refs/tags/([^{}]+)$")
CHANGELOG_HEADING_PATTERN = re.compile(
    r"^##\s+\[?v?(?P<version>[^\]\s-]+)\]?(?:\s+-.*)?$", re.MULTILINE
)


class TemplateService:
    def __init__(self, process: ProcessService | None = None) -> None:
        self.process = process or ProcessService()

    def latest_version(self, state: TemplateState, *, timeout: float = 5) -> str | None:
        if not state.source:
            return None
        source_path = Path(state.source).expanduser()
        try:
            if source_path.exists():
                result = self.process.run_git(["tag", "--list"], source_path, timeout=timeout)
                tags = result.stdout.splitlines()
            else:
                result = self.process.run_git(
                    ["ls-remote", "--tags", "--refs", state.source],
                    Path.cwd(),
                    timeout=timeout,
                )
                tags = []
                for line in result.stdout.splitlines():
                    match = TAG_PATTERN.search(line)
                    if match:
                        tags.append(match.group(1))
        except Exception:
            return None
        versions: list[tuple[Version, str]] = []
        for tag in tags:
            display = tag[1:] if tag.startswith("v") else tag
            try:
                parsed = Version(display)
            except InvalidVersion:
                continue
            if not parsed.is_prerelease:
                versions.append((parsed, display))
        return max(versions, default=(None, None), key=lambda item: item[0])[1]

    def changelog_changes(self, state: TemplateState) -> tuple[str, ...]:
        """Return the selected template version's Markdown changelog bullets.

        Changelog summaries are optional user experience enhancement; unavailable
        source metadata must never make an otherwise successful update fail.
        """
        if not state.source or not state.version:
            return ()
        try:
            content = self._changelog_at_version(state.source, state.version)
        except Exception:
            return ()
        if content is None:
            return ()
        return self._parse_changes(content, state.version)

    def _changelog_at_version(self, source: str, version: str) -> str | None:
        source_path = Path(source).expanduser()
        if source_path.exists():
            return self._show_changelog(source_path, version)
        try:
            with tempfile.TemporaryDirectory(prefix="marpme-changelog-") as temporary:
                for index, reference in enumerate(self._references(version)):
                    checkout = Path(temporary) / f"template-{index}"
                    try:
                        self.process.run_git(
                            ["clone", "--depth", "1", "--branch", reference, source, str(checkout)],
                            Path.cwd(),
                            timeout=15,
                        )
                    except Exception:
                        continue
                    try:
                        return (checkout / "CHANGELOG.md").read_text(encoding="utf-8")
                    except OSError:
                        return None
        except Exception:
            return None
        return None

    def _show_changelog(self, source: Path, version: str) -> str | None:
        for reference in self._references(version):
            try:
                return self.process.run_git(
                    ["show", f"{reference}:CHANGELOG.md"], source, timeout=5
                ).stdout
            except Exception:
                continue
        return None

    @staticmethod
    def _references(version: str) -> tuple[str, ...]:
        return (f"v{version}", version) if not version.startswith("v") else (version, version[1:])

    @staticmethod
    def _parse_changes(changelog: str, version: str) -> tuple[str, ...]:
        expected = version.removeprefix("v")
        matches = list(CHANGELOG_HEADING_PATTERN.finditer(changelog))
        for index, match in enumerate(matches):
            if match.group("version").removeprefix("v") != expected:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
            return tuple(
                line[2:].strip()
                for line in changelog[match.end() : end].splitlines()
                if line.startswith("- ") and line[2:].strip()
            )
        return ()
