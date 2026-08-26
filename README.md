# Marpme

Add a company-standard Marp presentation environment to an existing Git repository:

```console
marpme new architecture-review
```

Running `marpme` with no arguments creates `presentations/slidedeck`. The shorthand
`marpme architecture-review` is equivalent to the command above.

## Install

Windows (PowerShell 5.1 or newer):

```powershell
irm https://raw.githubusercontent.com/hacki11/marpme/main/packaging/install.ps1 | iex
```

Linux or WSL:

```sh
curl -fsSL https://raw.githubusercontent.com/hacki11/marpme/main/packaging/install.sh | sh
```

Inspect the downloaded installer before running it if required by your organization. Node users
can run the same standalone implementation ephemerally with `npx @company/marpme` or
`pnpm dlx @company/marpme`.

The installers use `https://github.com/hacki11/marpme/releases/latest/download/latest.json`.
Set `MARPME_RELEASE_MANIFEST` only when testing or mirroring releases. Standalone users need Git,
but do not need Python, Node.js, Copier, uv, or mise.

## Use

```console
marpme new customer-demo
marpme status
marpme doctor
marpme update
marpme update --to v1.7.0
marpme self update
```

The default template is `git@github.com:hacki11/marp-template.git`. It uses your normal Git/SSH
configuration and does not ask Marpme for a GitHub password. For local template development, pass
`--template ./path/to/template` and optionally `--template-ref v1.0.0`. Precedence is command-line
option, `MARPME_TEMPLATE_SOURCE`, then the compiled default.

Marpme owns scaffolding, template lifecycle, and repository/editor integration. Rendering remains
the responsibility of Marp/Marpit tooling.

## Template contract

The source must be a versioned Git repository containing a valid `copier.yml`. Copier renders it
into the repository root and records state in `.marpme/copier-answers.yml`. Shared, upgradeable files
belong under `.marpme/`. A template may create the first `presentations/<deck_name>/deck.md` itself.
For later decks it should provide a literal `.marpme/starter/` directory; Marpme copies that folder
without making the new deck part of Copier's managed update surface. If no starter is present,
Marpme creates a small standard deck.

`.marpme/config.yml` supports:

```yaml
version: 1
presentations_dir: presentations
template:
  channel: stable
```

## Development

Python 3.13 or newer is required for source development:

```console
uv sync
uv run pytest
uv run ruff check .
uv run marpme --help
```

The end-user artifacts are created with PyInstaller; Python is bundled and is not an end-user
prerequisite.
