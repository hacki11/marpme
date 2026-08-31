[CmdletBinding()]
param(
    [string]$ManifestUrl = $(if ($env:MARPME_RELEASE_MANIFEST) { $env:MARPME_RELEASE_MANIFEST } else { "https://github.com/hacki11/marpme/releases/latest/download/latest.json" }),
    [string]$InstallDirectory = $(if ($env:MARPME_INSTALL_DIR) { $env:MARPME_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "Programs\marpme\bin" })
)

$ErrorActionPreference = "Stop"

function Write-InstallerBanner {
    Write-Host ""
    Write-Host "      __  ___"
    Write-Host "     /  |/  /  marpme installer"
    Write-Host "    / /|_/ /   github.com/hacki11/marpme"
    Write-Host "   /_/  /_/"
    Write-Host ""
}

function Write-InstallerStatus([string]$Message) {
    Write-Host "  > $Message"
}

function Get-ReleaseManifest([string]$Uri) {
    $ProgressPreference = "SilentlyContinue"
    Invoke-RestMethod -Uri $Uri -Headers @{ "User-Agent" = "marpme-installer" }
}

function Save-ReleaseArtifact([string]$Uri, [string]$Destination) {
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $Uri -OutFile $Destination -UseBasicParsing
}

function Get-PathEntryKey([string]$Entry) {
    if ([string]::IsNullOrWhiteSpace($Entry)) {
        return ""
    }
    return (($Entry.Trim().Trim('"')) -replace '[\\/]+$', '').ToLowerInvariant()
}

function Prepend-PathEntry(
    [string]$PathValue,
    [string]$Entry,
    [string[]]$EntriesToRemove = @()
) {
    $entryKey = Get-PathEntryKey $Entry
    $removeKeys = @($EntriesToRemove | ForEach-Object { Get-PathEntryKey $_ })
    $segments = @($Entry)
    if (-not [string]::IsNullOrWhiteSpace($PathValue)) {
        $segments += $PathValue -split ";" | Where-Object {
            $key = Get-PathEntryKey $_
            $key -and $key -ne $entryKey -and $key -notin $removeKeys
        }
    }
    return $segments -join ";"
}

function Publish-EnvironmentChange {
    try {
        if (-not ("MarpmeInstaller.EnvironmentNativeMethods" -as [type])) {
            Add-Type -Namespace MarpmeInstaller -Name EnvironmentNativeMethods -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll", SetLastError = true, CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
public static extern System.IntPtr SendMessageTimeout(
    System.IntPtr hWnd,
    uint message,
    System.UIntPtr wParam,
    string lParam,
    uint flags,
    uint timeout,
    out System.UIntPtr result);
'@
        }
        $result = [UIntPtr]::Zero
        [MarpmeInstaller.EnvironmentNativeMethods]::SendMessageTimeout(
            [IntPtr]0xffff,
            0x1a,
            [UIntPtr]::Zero,
            "Environment",
            0x0002,
            1000,
            [ref]$result
        ) | Out-Null
    } catch {
        # The persistent and current-process PATH changes have already succeeded.
    }
}

Write-InstallerBanner

if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
    throw "This installer is for Windows. Use install.sh on Linux or WSL."
}

$architecture = switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()) {
    "X64" { "x86_64" }
    default { throw "Unsupported Windows architecture: $_" }
}
$platformKey = "windows-$architecture"
Write-InstallerStatus "detected windows/$architecture"
Write-InstallerStatus "fetching latest release manifest..."
$manifest = Get-ReleaseManifest $ManifestUrl
$artifact = $manifest.artifacts.$platformKey
if (-not $artifact -or -not $artifact.url -or $artifact.sha256.Length -ne 64) {
    throw "Release manifest has no valid artifact for $platformKey."
}

$temporary = Join-Path ([System.IO.Path]::GetTempPath()) ("marpme-" + [guid]::NewGuid() + ".exe")
try {
    $displayVersion = if (-not $manifest.version) {
        "latest release"
    } elseif ($manifest.version.ToString().StartsWith("v")) {
        $manifest.version.ToString()
    } else {
        "v$($manifest.version)"
    }
    Write-InstallerStatus "downloading $displayVersion..."
    Save-ReleaseArtifact $artifact.url $temporary
    Write-InstallerStatus "verifying checksum..."
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

    $defaultInstallDirectory = Join-Path $env:LOCALAPPDATA "Programs\marpme\bin"
    $legacyInstallDirectory = Join-Path $env:LOCALAPPDATA "marpme\bin"
    $obsoletePathEntries = if ((Get-PathEntryKey $InstallDirectory) -eq (Get-PathEntryKey $defaultInstallDirectory)) {
        @($legacyInstallDirectory)
    } else {
        @()
    }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $newUserPath = Prepend-PathEntry $userPath $InstallDirectory $obsoletePathEntries
    $userPathChanged = $newUserPath -cne $userPath
    if ($userPathChanged) {
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        Publish-EnvironmentChange
    }
    $env:Path = Prepend-PathEntry $env:Path $InstallDirectory $obsoletePathEntries

    Write-InstallerStatus "installed marpme to $installPath"
    if ($userPathChanged) {
        Write-InstallerStatus "updated PATH for this shell and future terminals"
    } else {
        Write-InstallerStatus "PATH is already configured for this shell and future terminals"
    }
    Write-Host ""
    Write-InstallerStatus "ready. run 'marpme' to get started."
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}
