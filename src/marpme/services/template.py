from __future__ import annotations

import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

from marpme.models import TemplateState
from marpme.services.process import ProcessService

TAG_PATTERN = re.compile(r"refs/tags/([^{}]+)$")


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
