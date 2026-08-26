from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Repository:
    root: Path

    @property
    def marpme_dir(self) -> Path:
        return self.root / ".marpme"

    @property
    def answers_file(self) -> Path:
        return self.marpme_dir / "copier-answers.yml"

    @property
    def legacy_answers_file(self) -> Path:
        return self.root / ".copier-answers.yml"

    @property
    def existing_answers_file(self) -> Path:
        return self.answers_file if self.answers_file.is_file() else self.legacy_answers_file

    @property
    def config_file(self) -> Path:
        return self.marpme_dir / "config.yml"

    @property
    def legacy_config_file(self) -> Path:
        return self.root / ".marpme.yml"

    @property
    def legacy_nested_config_file(self) -> Path:
        return self.marpme_dir / ".marpme.yml"

    @property
    def existing_config_file(self) -> Path:
        for path in (self.config_file, self.legacy_nested_config_file, self.legacy_config_file):
            if path.is_file():
                return path
        return self.config_file


@dataclass(frozen=True)
class MarpmeConfig:
    version: int = 1
    template_channel: str = "stable"


@dataclass(frozen=True)
class TemplateState:
    source: str | None
    version: str | None
    answers: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateResult:
    previous_version: str | None
    current_version: str | None
    conflicts: tuple[Path, ...] = ()
    changes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseArtifact:
    url: str
    sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
    version: str
    artifacts: dict[str, ReleaseArtifact]


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str = ""
