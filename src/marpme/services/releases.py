from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from packaging.version import InvalidVersion, Version
from platformdirs import user_cache_path, user_data_path

from marpme import __version__
from marpme.errors import InstallationNotOwnedError, ReleaseError
from marpme.models import ReleaseArtifact, ReleaseManifest
from marpme.services.config import release_manifest_url

CACHE_TTL_SECONDS = 24 * 60 * 60


class ReleaseService:
    def __init__(self, manifest_url: str | None = None) -> None:
        override = os.environ.get("MARPME_CACHE_DIR")
        self.cache_dir = Path(override) if override else user_cache_path("marpme")
        metadata_override = os.environ.get("MARPME_INSTALL_METADATA")
        self.install_metadata = (
            Path(metadata_override)
            if metadata_override
            else user_data_path("marpme") / "installation.json"
        )
        configured_url = os.environ.get("MARPME_RELEASE_MANIFEST")
        owned_url = self._installed_manifest_url() if not configured_url else None
        self.manifest_url = manifest_url or configured_url or owned_url or release_manifest_url()

    def _installed_manifest_url(self) -> str | None:
        try:
            metadata = json.loads(self.install_metadata.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(metadata, dict) and metadata.get("owner") == "marpme":
            value = metadata.get("manifest_url")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def platform_key() -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        architecture = {
            "x86_64": "x86_64",
            "amd64": "x86_64",
            "aarch64": "aarch64",
            "arm64": "aarch64",
        }.get(machine)
        os_name = {"windows": "windows", "linux": "linux"}.get(system)
        if not os_name or not architecture:
            raise ReleaseError(f"No Marpme release is available for {system}/{machine}.")
        return f"{os_name}-{architecture}"

    def fetch_manifest(self, *, timeout: float = 10) -> ReleaseManifest:
        try:
            request = urllib.request.Request(
                self.manifest_url,
                headers={"Accept": "application/json", "User-Agent": f"marpme/{__version__}"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ReleaseError(f"Could not fetch the Marpme release manifest: {exc}") from exc
        try:
            version = str(payload["version"])
            Version(version)
            raw_artifacts = payload["artifacts"]
            if not isinstance(raw_artifacts, dict):
                raise TypeError("artifacts must be an object")
            artifacts = {
                key: ReleaseArtifact(url=str(value["url"]), sha256=str(value["sha256"]).lower())
                for key, value in raw_artifacts.items()
            }
            if any(
                re.fullmatch(r"[0-9a-f]{64}", item.sha256) is None for item in artifacts.values()
            ):
                raise ValueError("invalid SHA-256")
        except (KeyError, TypeError, ValueError, InvalidVersion) as exc:
            raise ReleaseError(f"Invalid Marpme release manifest: {exc}") from exc
        return ReleaseManifest(version=version, artifacts=artifacts)

    def available_update(self, *, force: bool = False) -> str | None:
        if os.environ.get("MARPME_DISABLE_UPDATE_CHECK") == "1":
            return None
        cache_file = self.cache_dir / "release-check.json"
        now = time.time()
        if not force:
            cached = self._read_cache(cache_file)
            if cached and now - cached[0] < CACHE_TTL_SECONDS:
                return self._newer(cached[1])
        manifest = self.fetch_manifest(timeout=2 if not force else 10)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_json(
            cache_file,
            {
                "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "latest": manifest.version,
            },
        )
        return self._newer(manifest.version)

    def self_update(self) -> str:
        if os.environ.get("MARPME_EPHEMERAL") == "1":
            raise InstallationNotOwnedError(
                "This Marpme instance was launched through npx/pnpm.\n\n"
                "Install Marpme persistently to enable self-update:\n"
                "  Windows: install.ps1\n  Linux/WSL: install.sh"
            )
        metadata = self._owned_installation()
        manifest_url = metadata.get("manifest_url")
        if isinstance(manifest_url, str) and manifest_url:
            self.manifest_url = manifest_url
        manifest = self.fetch_manifest()
        if Version(manifest.version) <= Version(__version__):
            return __version__
        key = self.platform_key()
        artifact = manifest.artifacts.get(key)
        if artifact is None:
            raise ReleaseError(f"Release {manifest.version} has no artifact for {key}.")
        install_path = Path(str(metadata["install_path"])).resolve()
        self._download_and_replace(artifact, install_path)
        return manifest.version

    def _owned_installation(self) -> dict[str, object]:
        try:
            metadata = json.loads(self.install_metadata.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InstallationNotOwnedError(
                "This installation is not recorded as Marpme-owned.\n\n"
                "Reinstall with the canonical install script to enable self-update."
            ) from exc
        if not isinstance(metadata, dict) or metadata.get("owner") != "marpme":
            raise InstallationNotOwnedError(
                "Refusing to update an installation not owned by Marpme."
            )
        install_path = metadata.get("install_path")
        if not isinstance(install_path, str) or not Path(install_path).is_file():
            raise InstallationNotOwnedError("The recorded Marpme executable does not exist.")
        executable = Path(sys.executable).resolve()
        # Frozen builds run from the installed executable. Source invocations are allowed
        # only in tests that explicitly point metadata at sys.executable.
        if getattr(sys, "frozen", False) and executable != Path(install_path).resolve():
            raise InstallationNotOwnedError("The running executable is not the owned installation.")
        return metadata

    def _download_and_replace(self, artifact: ReleaseArtifact, install_path: Path) -> None:
        install_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".marpme-update-", dir=install_path.parent
        )
        temporary = Path(temporary_name)
        try:
            digest = hashlib.sha256()
            request = urllib.request.Request(
                artifact.url, headers={"User-Agent": f"marpme/{__version__}"}
            )
            with (
                os.fdopen(descriptor, "wb") as output,
                urllib.request.urlopen(request, timeout=30) as response,
            ):
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest().lower() != artifact.sha256:
                raise ReleaseError("Downloaded Marpme artifact failed SHA-256 verification.")
            temporary.chmod(temporary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            if platform.system().lower() == "windows":
                self._schedule_windows_replacement(temporary, install_path)
            else:
                os.replace(temporary, install_path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _schedule_windows_replacement(temporary: Path, install_path: Path) -> None:
        helper = temporary.with_suffix(".ps1")
        helper.write_text(
            "param($PidToWait,$Source,$Destination,$Helper)\n"
            "Wait-Process -Id $PidToWait -ErrorAction SilentlyContinue\n"
            "Move-Item -LiteralPath $Source -Destination $Destination -Force\n"
            "Remove-Item -LiteralPath $Helper -Force\n",
            encoding="utf-8",
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(helper),
                str(os.getpid()),
                str(temporary),
                str(install_path),
                str(helper),
            ],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )

    @staticmethod
    def _read_cache(path: Path) -> tuple[float, str] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            checked = datetime.fromisoformat(str(payload["checked_at"]).replace("Z", "+00:00"))
            latest = str(payload["latest"])
            Version(latest)
            return checked.timestamp(), latest
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, InvalidVersion):
            return None

    @staticmethod
    def _newer(latest: str) -> str | None:
        try:
            return latest if Version(latest) > Version(__version__) else None
        except InvalidVersion:
            return None

    @staticmethod
    def _atomic_json(path: Path, payload: object) -> None:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2)
                stream.write("\n")
            os.replace(name, path)
        except Exception:
            Path(name).unlink(missing_ok=True)
            raise
