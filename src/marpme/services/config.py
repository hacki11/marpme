from __future__ import annotations

import os

DEFAULT_TEMPLATE_SOURCE = "git@github.com:hacki11/marp-template.git"
DEFAULT_RELEASE_MANIFEST_URL = (
    "https://github.com/hacki11/marpme/releases/latest/download/latest.json"
)


def template_source(command_line: str | None = None) -> str:
    return command_line or os.environ.get("MARPME_TEMPLATE_SOURCE") or DEFAULT_TEMPLATE_SOURCE


def release_manifest_url() -> str:
    return os.environ.get("MARPME_RELEASE_MANIFEST", DEFAULT_RELEASE_MANIFEST_URL)
