from __future__ import annotations

import os
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml

from marpme.errors import InvalidConfigError
from marpme.models import MarpmeConfig

DEFAULT_TEMPLATE_SOURCE = "git@github.com:hacki11/marp-template.git"
DEFAULT_RELEASE_MANIFEST_URL = (
    "https://github.com/hacki11/marpme/releases/latest/download/latest.json"
)


def template_source(command_line: str | None = None) -> str:
    return command_line or os.environ.get("MARPME_TEMPLATE_SOURCE") or DEFAULT_TEMPLATE_SOURCE


def release_manifest_url() -> str:
    return os.environ.get("MARPME_RELEASE_MANIFEST", DEFAULT_RELEASE_MANIFEST_URL)


def load_config(path: Path) -> MarpmeConfig:
    if not path.exists():
        return MarpmeConfig()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise InvalidConfigError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise InvalidConfigError(f"{path} must contain a YAML object.")
    version = raw.get("version", 1)
    presentations_dir = raw.get("presentations_dir", "presentations")
    template = raw.get("template", {}) or {}
    if version != 1:
        raise InvalidConfigError(f"Unsupported Marpme configuration version: {version}")
    if not isinstance(presentations_dir, str) or not presentations_dir.strip():
        raise InvalidConfigError("presentations_dir must be a non-empty string.")
    # Validate both path dialects regardless of the host OS. A POSIX-rooted path
    # such as `/tmp/decks` is not considered absolute by WindowsPath, while a
    # drive or UNC path is not considered absolute by PosixPath. Config files
    # must remain safe when repositories move between Windows, WSL, and Linux.
    posix_path = PurePosixPath(presentations_dir.replace("\\", "/"))
    windows_path = PureWindowsPath(presentations_dir)
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or ".." in posix_path.parts
        or ".." in windows_path.parts
    ):
        raise InvalidConfigError("presentations_dir must stay within the repository.")
    if not isinstance(template, dict):
        raise InvalidConfigError("template must be a YAML object.")
    channel = template.get("channel", "stable")
    if channel != "stable":
        raise InvalidConfigError("Only the stable template channel is supported.")
    return MarpmeConfig(
        version=version,
        presentations_dir=posix_path.as_posix(),
        template_channel=channel,
    )
