# marpme

Add a company-standard Marp presentation environment to an existing Git repository:

```console
marpme new architecture-review
```

Running `marpme` with no arguments creates `slidedeck`. The shorthand
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
configuration and does not ask marpme for a GitHub password. For local template development, pass
`--template ./path/to/template` and optionally `--template-ref v1.0.0`. Precedence is command-line
option, `MARPME_TEMPLATE_SOURCE`, then the compiled default.

marpme owns scaffolding, template lifecycle, and repository/editor integration. Rendering remains
the responsibility of Marp/Marpit tooling.

Long-running Git, Copier, and network operations show a live spinner with the current stage in an
interactive terminal. Redirected output and CI logs receive the same stages as ordinary lines.

## Template contract

The source must be a versioned Git repository containing a valid `copier.yml`. Copier renders it
into the repository root and records state in `.marpme/copier-answers.yml`. Shared, upgradeable files
belong under `.marpme/`; themes conventionally live in `.marpme/themes/`. The template must provide
a literal `.marpme/starter/` directory. marpme copies that folder for every new deck without making
the deck part of Copier's managed update surface. If no starter is present, marpme stops with an
error rather than creating deck content itself.

Templates may provide `.vscode/extensions.json`, `.vscode/settings.json`, and `.vscode/tasks.json`
at their repository root. marpme reads these files from the selected template revision and merges
missing properties and array entries into the target workspace. Existing scalar settings and tasks
with an existing label remain user-owned. Templates should exclude `.vscode/` from Copier so Copier
does not overwrite existing workspace configuration.

marpme records the applied editor configuration in `.marpme/vscode-template-state.json`. Template
updates use that baseline for a semantic three-way merge: unchanged template entries can be updated
or removed, user-only changes survive, and simultaneous edits are reported as configuration
conflicts while preserving the user's value.

Templates must maintain a versioned, parseable `CHANGELOG.md`. After a template update, marpme
shows the bullet-point changes recorded for the installed version when that file is available.

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
