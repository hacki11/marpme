[CmdletBinding()]
param(
    [string]$ManifestUrl = $(if ($env:MARPME_RELEASE_MANIFEST) { $env:MARPME_RELEASE_MANIFEST } else { "https://github.com/hacki11/marpme/releases/latest/download/latest.json" }),
    [string]$InstallDirectory = $(if ($env:MARPME_INSTALL_DIR) { $env:MARPME_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "marpme\bin" })
)

$ErrorActionPreference = "Stop"
if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
    throw "This installer is for Windows. Use install.sh on Linux or WSL."
}

$architecture = switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()) {
    "X64" { "x86_64" }
    default { throw "Unsupported Windows architecture: $_" }
}
$platformKey = "windows-$architecture"
$manifest = Invoke-RestMethod -Uri $ManifestUrl -Headers @{ "User-Agent" = "marpme-installer" }
$artifact = $manifest.artifacts.$platformKey
if (-not $artifact -or -not $artifact.url -or $artifact.sha256.Length -ne 64) {
    throw "Release manifest has no valid artifact for $platformKey."
}

$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("marpme-" + [guid]::NewGuid() + ".exe")
try {
    Invoke-WebRequest -Uri $artifact.url -OutFile $temporary -UseBasicParsing
    $actualHash = (Get-FileHash -Path $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $artifact.sha256.ToLowerInvariant()) {
        throw "Checksum verification failed; marpme was not installed."
    }
    New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    $installPath = Join-Path $InstallDirectory "marpme.exe"
    Move-Item -LiteralPath $temporary -Destination $installPath -Force

    $metadataDirectory = Join-Path $env:LOCALAPPDATA "marpme"
    New-Item -ItemType Directory -Path $metadataDirectory -Force | Out-Null
    @{
        owner = "marpme"
        install_path = $installPath
        manifest_url = $ManifestUrl
    } | ConvertTo-Json | Set-Content -Path (Join-Path $metadataDirectory "installation.json") -Encoding UTF8

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @($userPath -split ";" | Where-Object { $_ })
    if ($entries -notcontains $InstallDirectory) {
        [Environment]::SetEnvironmentVariable("Path", (($entries + $InstallDirectory) -join ";"), "User")
        Write-Host "Added $InstallDirectory to your user PATH. Open a new terminal."
    }
    Write-Host "marpme installed at $installPath"
    Write-Host "Run: marpme --version"
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}
