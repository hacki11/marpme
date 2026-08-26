from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

import pytest

from marpme.errors import InstallationNotOwnedError, ReleaseError
from marpme.services.releases import ReleaseService


def test_platform_key_is_supported() -> None:
    assert ReleaseService.platform_key() in {
        "linux-x86_64",
        "linux-aarch64",
        "windows-x86_64",
        "windows-aarch64",
    }


def test_manifest_parsing_and_checksum_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"standalone executable")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = tmp_path / "latest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "99.0.0",
                "artifacts": {
                    ReleaseService.platform_key(): {
                        "url": artifact.as_uri(),
                        "sha256": digest,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    installed = tmp_path / "marpme"
    installed.write_bytes(b"old")
    metadata = tmp_path / "installation.json"
    metadata.write_text(
        json.dumps(
            {
                "owner": "marpme",
                "install_path": str(installed),
                "manifest_url": manifest.as_uri(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARPME_INSTALL_METADATA", str(metadata))
    service = ReleaseService(manifest.as_uri())
    scheduler = (
        "_schedule_windows_replacement"
        if platform.system().lower() == "windows"
        else "_schedule_posix_replacement"
    )
    monkeypatch.setattr(
        service, scheduler, lambda source, destination: os.replace(source, destination)
    )
    assert service.self_update() == "99.0.0"
    assert installed.read_bytes() == b"standalone executable"
    assert installed.stat().st_mode & 0o100


def test_posix_replacement_is_deferred_until_process_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temporary = tmp_path / ".marpme-update"
    installed = tmp_path / "marpme"
    popen_call: dict[str, object] = {}

    def record_popen(args: list[str], **kwargs: object) -> None:
        popen_call["args"] = args
        popen_call["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", record_popen)

    ReleaseService._schedule_posix_replacement(temporary, installed)

    args = popen_call["args"]
    assert isinstance(args, list)
    assert args[:2] == ["/bin/sh", "-c"]
    assert "kill -0" in args[2]
    assert args[4:] == [str(os.getpid()), str(temporary), str(installed)]
    kwargs = popen_call["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["start_new_session"] is True
    assert kwargs["close_fds"] is True


def test_bad_checksum_does_not_replace_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "artifact"
    artifact.write_bytes(b"new")
    installed = tmp_path / "marpme"
    installed.write_bytes(b"old")
    manifest = tmp_path / "latest.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "99.0.0",
                "artifacts": {
                    ReleaseService.platform_key(): {
                        "url": artifact.as_uri(),
                        "sha256": "0" * 64,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    metadata = tmp_path / "installation.json"
    metadata.write_text(
        json.dumps({"owner": "marpme", "install_path": str(installed)}),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARPME_INSTALL_METADATA", str(metadata))
    with pytest.raises(ReleaseError, match="SHA-256"):
        ReleaseService(manifest.as_uri()).self_update()
    assert installed.read_bytes() == b"old"


def test_ephemeral_installation_refuses_self_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARPME_EPHEMERAL", "1")
    with pytest.raises(InstallationNotOwnedError, match="npx/pnpm"):
        ReleaseService().self_update()
