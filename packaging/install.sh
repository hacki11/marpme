#!/bin/sh
set -eu

manifest_url=${MARPME_RELEASE_MANIFEST:-https://github.com/hacki11/marpme/releases/latest/download/latest.json}
install_dir=${MARPME_INSTALL_DIR:-"${HOME}/.local/bin"}
data_home=${XDG_DATA_HOME:-"${HOME}/.local/share"}
metadata_dir="${data_home}/marpme"

case "$(uname -s)" in
  Linux) os_name=linux ;;
  *) printf '%s\n' "marpme supports Linux and WSL through this installer." >&2; exit 1 ;;
esac

case "$(uname -m)" in
  x86_64|amd64) architecture=x86_64 ;;
  aarch64|arm64) architecture=aarch64 ;;
  *) printf 'Unsupported architecture: %s\n' "$(uname -m)" >&2; exit 1 ;;
esac

platform_key="${os_name}-${architecture}"
temporary_dir=$(mktemp -d)
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
manifest_file="${temporary_dir}/latest.json"
curl -fsSL --retry 3 --connect-timeout 10 "$manifest_url" -o "$manifest_file"

# The release manifest has a deliberately small schema. Flattening it makes extraction portable
# without requiring jq, Python, or Node on the target machine.
manifest=$(tr -d '\n\r' < "$manifest_file")
artifact_block=$(printf '%s' "$manifest" | sed -n "s/.*\"${platform_key}\"[[:space:]]*:[[:space:]]*{\([^}]*\)}.*/\1/p")
artifact_url=$(printf '%s' "$artifact_block" | sed -n 's/.*"url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
artifact_sha=$(printf '%s' "$artifact_block" | sed -n 's/.*"sha256"[[:space:]]*:[[:space:]]*"\([0-9a-fA-F]*\)".*/\1/p' | tr 'A-F' 'a-f')

if [ -z "$artifact_url" ] || [ "${#artifact_sha}" -ne 64 ]; then
  printf 'Release manifest has no valid artifact for %s.\n' "$platform_key" >&2
  exit 1
fi

download="${temporary_dir}/marpme"
curl -fsSL --retry 3 --connect-timeout 10 "$artifact_url" -o "$download"
actual_sha=$(sha256sum "$download" | awk '{print $1}')
if [ "$actual_sha" != "$artifact_sha" ]; then
  printf '%s\n' "Checksum verification failed; marpme was not installed." >&2
  exit 1
fi

mkdir -p "$install_dir" "$metadata_dir"
chmod 0755 "$download"
mv "$download" "${install_dir}/marpme"
cat > "${metadata_dir}/installation.json" <<EOF
{
  "owner": "marpme",
  "install_path": "${install_dir}/marpme",
  "manifest_url": "${manifest_url}"
}
EOF

printf 'marpme installed at %s\n' "${install_dir}/marpme"
case ":${PATH}:" in
  *":${install_dir}:"*) ;;
  *) printf 'Add %s to PATH, then run: marpme --version\n' "$install_dir" ;;
esac
