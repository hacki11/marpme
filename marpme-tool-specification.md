# Marpme CLI — Product & Technical Specification

**Status:** Draft implementation specification  
**Audience:** AI coding agent / implementation team  
**Primary implementation language:** Python  
**Primary template engine / lifecycle manager:** Copier  
**CLI name:** `marpme`

---

## 1. Purpose

`marpme` is a cross-platform command-line tool for adding and maintaining company-standard Marp presentations inside an existing software repository.

The tool replaces the current workflow in which users must:

- clone a dedicated Marp template repository,
- create their presentation inside that repository, or
- add the template repository as a Git submodule.

The desired experience is:

```bash
marpme new architecture-review
```

or, optionally, the shorthand:

```bash
marpme architecture-review
```

The command initializes a presentation folder inside the user's current repository and integrates the company slide template, theme assets, AI skills, and recommended editor configuration.

`marpme` is intentionally **not** a renderer, preview server, Marp runtime manager, or replacement for existing Marp/Marpit tooling. Its responsibility ends at repository scaffolding, template lifecycle management, and editor/workspace integration.

The created presentation must remain connected to the upstream template so that future template releases can be applied later using:

```bash
marpme update
```

Template updates must use **Copier's update / merge capabilities** rather than a custom overwrite or synchronization implementation.

---

# 2. Product Goals

## 2.1 Primary goals

The tool must provide:

1. **One-command presentation creation**
   - User starts inside an existing repository.
   - User runs `marpme new <deck-name>`.
   - A ready-to-edit Marp presentation is created.

2. **Minimal machine prerequisites**
   - Users must not be required to install Python, Node.js, mise, Copier, or another runtime to use the default distribution.
   - A standalone binary must be available for Windows and Linux.

3. **Template lifecycle management**
   - Presentations stay linked logically to the canonical template.
   - Users can apply newer template releases.
   - Local modifications must be merged using Copier.

4. **Simple, owned installation lifecycle**
   - standalone executable,
   - PowerShell bootstrap as the canonical Windows installation,
   - shell bootstrap as the canonical Linux/WSL installation,
   - npm/npx and pnpm only as zero-install ephemeral launchers,
   - self-update owned by Marpme for canonical installations.

5. **Cross-platform behavior**
   - Native Windows.
   - Linux.
   - WSL.
   - The same CLI commands and semantics should work everywhere.

6. **Good repository citizenship**
   - Do not overwrite arbitrary existing user files.
   - Merge shared repository configuration where possible.
   - Keep presentation-specific state localized.

7. **Excellent developer UX**
   - concise human-readable output,
   - useful errors,
   - rich status messages,
   - actionable diagnostics,
   - no unnecessary prompts.

8. **AI-first presentation workflow**
   - Company AI skills/instructions should be installed with the presentation environment.
   - AI-related assets must participate in template versioning and updates.

---

# 2.2 Product boundary

`marpme` owns only three capability areas:

1. **Scaffolding**
   - initialize the repository-level slide environment,
   - create new deck folders from the company template,
   - install/update shared theme, skill, and support files.

2. **Template lifecycle**
   - track the template source/version,
   - apply upstream template releases,
   - delegate update/merge semantics to Copier,
   - surface merge conflicts clearly.

3. **Repository and VS Code integration**
   - merge extension recommendations,
   - optionally merge small required workspace settings,
   - keep shared slide infrastructure organized inside the repository.

`marpme` must not depend on Marp CLI or Marpit at runtime. Generated files may naturally be intended for use with Marp, but Marp itself is outside this tool's architecture.

---

# 3. Non-Goals

The first implementation must NOT attempt to:

- render Marp slides,
- provide preview/watch/server functionality,
- generate PDF, PPTX, HTML, or images,
- bundle or manage Marp CLI,
- expose Marp CLI arguments through a wrapper command,
- replace Marp or Marpit,
- replace Copier,
- implement a custom template merge algorithm,
- implement a Git replacement,
- implement a package manager,
- automatically install arbitrary VS Code extensions without user consent,
- silently modify unrelated repository configuration,
- build a VS Code extension,
- provide a GUI,
- provide cloud synchronization,
- provide a presentation editor,
- require Docker,
- require mise.

The boundary is strict:

```text
marpme = scaffold + update + repository integration
Marp/Marpit = rendering ecosystem, outside marpme
```


---

# 4. User Experience

## 4.1 Typical first-time flow

User is inside an existing repository:

```text
my-product/
├── src/
├── tests/
├── .git/
└── README.md
```

User may run the zero-argument shortcut:

```bash
marpme
```

which creates:

```text
slidedeck/
```

For an explicitly named deck, the user runs:

```bash
marpme new architecture-review
```

Expected result:

```text
✓ Repository detected
✓ Marpme environment initialized
✓ Template 1.4.0 applied
✓ Presentation created: architecture-review
✓ Company Marp theme added
✓ AI presentation skill added
✓ VS Code Marp extension recommended

Next:
  edit architecture-review/deck.md
```

Resulting repository:

```text
my-product/
├── src/
├── tests/
├── architecture-review/
│   ├── deck.md
│   ├── assets/
│   └── ...
├── .marpme/
│   ├── ...
│   └── ...
├── .vscode/
│   └── extensions.json
└── ...
```

The exact repository layout is defined later in this specification.

---

# 5. High-Level Architecture

```text
                       Canonical Git repositories
                 ┌──────────────────────────────────┐
                 │ marpme-template                  │
                 │                                  │
                 │ copier.yml                       │
                 │ template files                   │
                 │ CSS / assets                     │
                 │ AI skills                        │
                 │ VS Code fragments                │
                 │ migrations                       │
                 └──────────────┬───────────────────┘
                                │
                           Git tags/releases
                                │
                                ▼
                    ┌───────────────────────┐
                    │       marpme CLI      │
                    │                       │
                    │ Python                │
                    │ Typer                 │
                    │ Rich                  │
                    │ Copier API            │
                    │ repository services   │
                    └───────────┬───────────┘
                                │
                                ▼
                     User's existing repository
```

Distribution is independent from implementation, but the canonical lifecycle is intentionally narrow:

```text
                    Python source
                        │
                    PyInstaller
                        │
                standalone binaries
                        │
             ┌──────────┴──────────┐
             │                     │
        install.ps1           install.sh
        Windows               Linux / WSL
             │                     │
             └──────────┬──────────┘
                        │
                  Marpme-owned install
                        │
                 marpme self update

Optional zero-install entry points:

  npx @company/marpme
  pnpm dlx @company/marpme
```

These npm/pnpm entry points launch Marpme ephemerally and do not own a persistent installation.

---

# 6. Technology Stack

## 6.1 Application

Use:

- **Python 3.13+** where practical.
- **Typer** for CLI command structure.
- **Rich** for terminal output.
- **Copier** as the template generation and update engine.
- **pytest** for tests.
- **ruff** for linting/formatting.
- **uv** for development dependency management and local execution only; it is not part of the user-facing installation model.

Recommended project structure:

```text
marpme/
├── pyproject.toml
├── README.md
├── src/
│   └── marpme/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── commands/
│       │   ├── new.py
│       │   ├── update.py
│       │   ├── status.py
│       │   ├── doctor.py
│       │   └── upgrade.py
│       ├── services/
│       │   ├── repository.py
│       │   ├── copier_service.py
│       │   ├── vscode.py
│       │   ├── template.py
│       │   ├── releases.py
│       │   ├── tools.py
│       │   └── process.py
│       ├── models/
│       └── errors.py
├── tests/
└── packaging/
    ├── pyinstaller/
    ├── npm/
    ├── install.ps1
    └── install.sh
```

---

# 7. Template Repository

The upstream presentation template must be a normal Git repository and a valid Copier template.

Example:

```text
marpme-template/
├── copier.yml
├── template/
│   ├── ...
│   └── ...
├── CHANGELOG.md
└── README.md
```

Template versions must be released using Git tags, preferably semantic versions:

```text
v1.0.0
v1.1.0
v1.2.0
v2.0.0
```

`marpme` must prefer stable tagged releases rather than arbitrary branch heads.

---

# 8. Repository Layout

The recommended model is **one Marpme environment per repository** with multiple decks below it.

Example:

```text
repo/
├── .git/
│
├── .marpme/
│   ├── config/
│   ├── theme/
│   ├── skills/
│   ├── scripts/
│   ├── metadata/
│   └── ...
│
├── architecture-review/
│   ├── deck.md
│   ├── assets/
│   └── custom.css
│
├── customer-demo/
│   ├── deck.md
│   ├── assets/
│   └── custom.css
│
├── .vscode/
│   └── extensions.json
│
└── ...
```

Advantages:

- template-managed tooling is not duplicated per presentation,
- all decks in one repository use a consistent template version,
- updates are easier,
- AI skills are shared,
- CSS and helper scripts are shared.

---

# 9. Ownership Model

Files must conceptually fall into two categories.

## 9.1 Template-managed files

Examples:

```text
.marpme/theme/**
.marpme/skills/**
.marpme/scripts/**
.marpme/config/**
```

These originate from the template and are updated using Copier.

Users may modify them, but modifications become part of Copier's merge/update behavior.

## 9.2 User-owned files

Examples:

```text
<deck-name>/deck.md
<deck-name>/assets/**
<deck-name>/custom.css
```

These contain presentation-specific user work.

The template may create initial versions but must avoid unnecessary later ownership of deck content.

The template should be designed to minimize update conflicts.

---

# 10. Copier Integration

Copier is a core implementation dependency.

The CLI must use Copier's Python API where possible.

Do not shell out to the `copier` executable unless necessary.

Conceptual integration:

```python
from copier import run_copy, run_update
```

The implementation must encapsulate Copier behind a local service interface.

Example conceptual API:

```python
class CopierService:
    def create_repository_environment(...):
        ...

    def update_repository_environment(...):
        ...

    def get_current_template_version(...):
        ...
```

The rest of the application must not depend directly on Copier internals.

This allows future replacement or changes without altering the public CLI.

---

# 11. Copier State

The generated repository must retain Copier metadata required for later updates.

The exact filename and format should follow Copier's supported mechanism.

Typical example:

```text
.marpme/copier-answers.yml
```

The metadata must include sufficient information to identify:

- template source,
- source template version,
- template answers,
- relevant configuration.

Do not invent a parallel merge-state system if Copier already provides the necessary state.

---

# 12. Template Update Workflow

Command:

```bash
marpme update
```

Expected behavior:

1. detect repository root,
2. detect whether Marpme is initialized,
3. determine current template version,
4. determine latest allowed template version,
5. show upgrade information,
6. verify repository state is safe enough for update,
7. run Copier update,
8. surface conflicts clearly,
9. update local Marpme metadata if necessary,
10. print summary.

Example:

```text
$ marpme update

Current template: 1.4.0
Latest template:  1.6.0

Updating...

✓ Template fetched
✓ Copier update completed
✓ VS Code integration checked

Updated to 1.6.0
```

If conflicts occur:

```text
! Template update completed with conflicts

Conflicts:
  .marpme/theme/company.css
  .marpme/skills/slides/SKILL.md

Resolve the conflict markers, commit the result, then continue normally.
```

Do not hide merge conflicts.

---

# 13. Git Behavior

Git is allowed as a practical prerequisite because the primary target use case is an existing source repository.

However:

- Python must not be a prerequisite.
- Copier must not be a prerequisite.
- Node must not be a prerequisite.
- mise must not be a prerequisite.

`marpme doctor` must detect whether Git is available.

Where Copier requires Git operations, the tool must provide a helpful error if Git is unavailable.

Example:

```text
Git is required to update Marpme templates.

Install Git and retry:
  https://git-scm.com/
```

For internal environments, documentation may point to a company-specific installation source instead.

---

# 14. CLI Commands

## 14.1 `marpme new`

```bash
marpme new <name>
```

Creates a new deck inside the current repository.

Default target:

```text
<name>/
```

Example:

```bash
marpme new architecture-review
```

Behavior:

- locate repository root,
- initialize repository-level Marpme environment if absent,
- create deck folder,
- copy/create starter deck,
- ensure editor integration,
- report completion.

Must be idempotent where possible.

If deck already exists, do not overwrite silently.

---

## 14.2 Shorthand command

Optional:

```bash
marpme <name>
```

Equivalent to:

```bash
marpme new <name>
```

Only implement if it does not make CLI parsing or future subcommands ambiguous.

The explicit `new` form remains canonical.

---

## 14.3 `marpme update`

```bash
marpme update
```

Updates the repository's Marpme template using Copier.

Optional:

```bash
marpme update --to 1.7.0
```

or:

```bash
marpme update --to latest
```

Only add explicit version selection if straightforward.

---

## 14.4 `marpme status`

```bash
marpme status
```

Example:

```text
Marpme

CLI       0.8.1
Template  1.4.0
Latest    1.6.0

Decks
  architecture-review
  customer-demo

Template update available.
```

Status should be fast and must not unnecessarily mutate anything.

---

## 14.5 `marpme doctor`

```bash
marpme doctor
```

Checks:

- repository found,
- Git installed,
- Marpme initialized,
- template metadata valid,
- VS Code integration valid,
- connectivity to template source where appropriate.

Example:

```text
$ marpme doctor

✓ Git
✓ Repository
✓ Marpme metadata
✓ Template source reachable
✓ VS Code recommendation
```

---

## 14.6 `marpme self update`

```bash
marpme self update
```

Updates the **Marpme CLI itself** for installations owned by Marpme.

This is intentionally distinct from:

```bash
marpme update
```

which updates the **slide template/workspace in the current repository**.

Terminology:

```text
marpme self update   -> update the Marpme CLI
marpme update        -> update the repository template
```

`marpme self update` must perform a fresh version check, download the correct platform artifact, verify integrity, and replace the current installation safely.

For ephemeral invocations through `npx` or `pnpm dlx`, self-update must not modify package-manager caches. It should explain that self-update is available only for a canonical Marpme installation and point to the install-script flow.

## 14.7 `marpme version`

Support:

```bash
marpme --version
```

Output:

```text
marpme 0.8.1
```

---

# 15. Repository Detection

When executed, the CLI must locate the working repository.

Recommended behavior:

1. Start from current working directory.
2. Walk upward until `.git` or another repository marker is found.
3. Treat that directory as repository root.
4. If no repository is found, either:
   - fail by default, or
   - support `--no-git` later if desired.

Default failure:

```text
No Git repository found.

Run marpme from inside a repository.
```

Do not initialize Git automatically unless explicitly requested by a future feature.

---

# 16. Naming Rules

Deck names must be safe as folder names.

Recommended accepted form:

```text
[a-zA-Z0-9][a-zA-Z0-9._-]*
```

Normalize only when clearly safe.

Prefer rejecting ambiguous names over silently rewriting them.

Examples:

Valid:

```text
architecture-review
Q4-review
demo_2026
```

Invalid:

```text
../../foo
foo/bar
```

Prevent path traversal.

---

# 17. VS Code Integration

The tool should integrate with VS Code without taking ownership of the user's workspace.

## 17.1 Extension recommendations

Use:

```text
.vscode/extensions.json
```

Recommend the official Marp VS Code extension.

Example:

```json
{
  "recommendations": [
    "marp-team.marp-vscode"
  ]
}
```

If the file already exists:

- parse existing JSON,
- preserve existing recommendations,
- add missing recommendation,
- avoid duplicates.

Never replace the whole file unless it was created by Marpme and no merge is needed.

Do not automatically install the extension.

---

## 17.2 Settings

Avoid modifying `.vscode/settings.json` unless required.

If settings are necessary:

- merge only required keys,
- preserve unrelated keys,
- warn before replacing conflicting values.

Prefer presentation-local configuration over root workspace configuration.

---

## 17.3 Tasks

Avoid generating one VS Code task per presentation.

Preferred design:

- generic CLI commands,
- optionally one generic Marpme VS Code task,
- let users run:

```bash
```

rather than tightly coupling the workflow to VS Code.

---

# 18. AI Skill Integration

The company AI skill must be part of the upstream template.

Example:

```text
.marpme/
└── skills/
    └── slides/
        ├── SKILL.md
        ├── brand.md
        ├── diagrams.md
        └── examples/
```

The AI skill should contain:

- allowed colors,
- typography rules,
- spacing rules,
- supported visual primitives,
- SVG snippets,
- diagram conventions,
- layout guidance,
- anti-patterns,
- company presentation rules.

Because these files are part of the template, they are versioned and updated through Copier.

---

# 19. Template Design Principles

The template must be designed specifically for long-lived upgrades.

Rules:

1. Minimize generated files that users are expected to modify heavily.
2. Separate reusable infrastructure from deck content.
3. Avoid embedding giant generated configurations into user files.
4. Prefer small stable interfaces between user content and template-managed content.
5. Keep deck-specific content independent from template internals.
6. Treat template changes as versioned API changes.

A bad template design creates unavoidable conflicts on every update.

A good template design lets most updates touch only shared infrastructure.

---

# 20. Template Versioning

Use semantic versioning.

Interpretation:

### Patch

```text
1.4.0 -> 1.4.1
```

Examples:

- typo fixes,
- CSS fixes,
- AI skill wording fixes,
- minor script fixes.

### Minor

```text
1.4.0 -> 1.5.0
```

Examples:

- new layouts,
- new skill features,
- new helper scripts,
- backward-compatible config additions.

### Major

```text
1.x -> 2.0
```

Examples:

- changed repository layout,
- incompatible Marp config,
- renamed theme interface,
- breaking skill structure,
- migration required.

---

# 21. Template Changelog

Each release must include machine-readable or easily parseable release information.

Minimum:

```text
CHANGELOG.md
```

Preferred optional metadata:

```json
{
  "version": "1.6.0",
  "changes": [
    "Improved title slide layout",
    "Added architecture diagram primitives",
    "Updated AI skill rules"
  ]
}
```

`marpme status` or `marpme update` may show these changes.

---

# 22. Configuration

Repository-level config should be minimal.

Potential file:

```text
.marpme/config.yml
```

Example:

```yaml
version: 1

template:
  channel: stable
```

Do not duplicate data already managed by Copier unless needed for Marpme-specific behavior.

Keep the configuration format stable and versioned.

---

# 23. Logging and Terminal UX

Default output should be concise and human-oriented.

Use Rich for:

- status markers,
- tables,
- emphasis,
- progress indicators when appropriate.

Avoid excessive animations.

Example:

```text
Creating presentation "architecture-review"

✓ Repository detected
✓ Template 1.6.0
✓ Presentation files
✓ AI skill
✓ VS Code integration

Created:
  architecture-review/deck.md
```

Support:

```bash
marpme --verbose ...
```

for detailed diagnostics.

Optionally support:

```bash
marpme --json ...
```

later for automation.

---

# 24. Error Handling

Errors must be actionable.

Bad:

```text
Error: subprocess exited 1
```

Good:

```text
Template update failed because the repository has unresolved Git conflicts.

Resolve the existing conflicts and retry:
  marpme update
```

Define application-specific error classes.

Suggested categories:

- repository not found,
- invalid repository state,
- template unavailable,
- Copier failure,
- Git missing,
- merge conflict,
- invalid config,
- network failure,
- permission failure,
- deck already exists.

---

# 25. Safety Around Existing Files

The CLI must not blindly overwrite existing files.

For repository-level JSON such as:

```text
.vscode/extensions.json
```

perform structured merge.

For template-controlled files:

- use Copier behavior.

For user-owned deck directories:

- fail if target exists unless a dedicated explicit option is provided.

Potential explicit override:

```bash
marpme new foo --force
```

`--force` must never delete unrelated repository files.

---

# 26. Security Requirements

## 26.1 Installer integrity

Canonical installers must verify downloads.

Release artifacts must publish SHA-256 checksums, preferably in:

```text
SHA256SUMS
```

Artifact signing may be added later.

## 26.2 PowerShell installer

The canonical Windows installation is a user-local bootstrap script.

Fast path:

```powershell
irm https://company.example/marpme/install.ps1 | iex
```

Also document an inspectable form:

```powershell
irm https://company.example/marpme/install.ps1 -OutFile install-marpme.ps1
.\install-marpme.ps1
```

The installer must:

1. detect OS/architecture,
2. download the correct Marpme binary,
3. verify checksum,
4. install into a user-writable Marpme-owned location,
5. add that location to the user PATH where possible,
6. record enough installation metadata for safe self-update,
7. print next steps.

No administrator privileges should be required for the default user-local installation.

Suggested Windows location:

```text
%LOCALAPPDATA%\Marpme\bin\marpme.exe
```

# 27. Linux / WSL Installer

Provide:

```bash
curl -fsSL https://company.example/marpme/install.sh | sh
```

Also document the inspect-first variant.

Install location should normally be user-writable and Marpme-owned, for example:

```text
~/.local/bin/marpme
```

The installer must:

- detect CPU architecture,
- download the matching artifact,
- verify checksum,
- ensure the install directory exists,
- warn if the install directory is not on PATH,
- record enough installation metadata for safe self-update.

WSL uses the Linux installation path and Linux binary.

# 28. Standalone Binary Packaging

Use **PyInstaller** initially.

Target release artifacts:

```text
marpme-windows-x86_64.exe
marpme-linux-x86_64
marpme-linux-aarch64
```

Optional later:

```text
marpme-darwin-arm64
marpme-darwin-x86_64
```

Each platform must be built on a compatible build runner.

Do not rely on cross-compiling PyInstaller artifacts from one OS to another.

A one-file executable is preferred for installation simplicity unless startup or packaging reliability becomes problematic.

---

# 29. npm / npx / pnpm Distribution

Publish a lightweight npm package:

```text
@company/marpme
```

Supported zero-install usage:

```bash
npx @company/marpme
```

and:

```bash
pnpm dlx @company/marpme
```

The npm package must not contain a second implementation of the CLI.

It acts only as an ephemeral launcher for the platform-specific standalone Marpme binary.

Recommended behavior:

1. detect OS and architecture,
2. resolve the matching Marpme release artifact,
3. download or use an npm-packaged platform artifact,
4. cache it only as appropriate for the npm execution model,
5. execute it with the user's arguments.

The npm/pnpm path is explicitly **not** the canonical persistent installation lifecycle.

When invoked ephemerally, Marpme must not attempt to overwrite npm or pnpm caches during `marpme self update`.

Instead, show a concise message such as:

```text
This Marpme instance was launched through npx/pnpm.

Install Marpme persistently to enable self-update:
  Windows: install.ps1
  Linux/WSL: install.sh
```

Do not advertise global npm installation as the primary path.

# 30. Unsupported / Non-Primary Distribution Channels

The following mechanisms are intentionally not part of the v1 user-facing installation story:

- pip,
- pipx,
- `uv tool install`,
- mise,
- Homebrew,
- Linux distribution package managers.

Python remains an implementation detail.

These channels may be added later if there is a concrete organizational need, but they must not complicate the canonical self-update lifecycle.

# 31. Release Architecture

The release pipeline is the single source of truth for versioned binaries.

Example:

```text
Git tag
  v0.8.0
     │
     ▼
CI release pipeline
     │
     ├── Windows build
     │      └── marpme-windows-x86_64.exe
     │
     ├── Linux x64 build
     │      └── marpme-linux-x86_64
     │
     ├── Linux ARM64 build
     │      └── marpme-linux-aarch64
     │
     ├── SHA256SUMS
     ├── latest.json release manifest
     ├── install.ps1
     ├── install.sh
     └── npm launcher/package publish
```

The release manifest must be suitable for both update notifications and `marpme self update`.

# 33. Release Architecture

The release pipeline should be the single source of truth for versioned binaries.

Example:

```text
Git tag
  v0.8.0
     │
     ▼
CI release pipeline
     │
     ├── Windows build
     │      └── marpme-windows-x86_64.exe
     │
     ├── Linux x64 build
     │      └── marpme-linux-x86_64
     │
     ├── Linux ARM64 build
     │      └── marpme-linux-aarch64
     │
     ├── SHA256SUMS
     │
     ├── PyPI publish
     │
     ├── npm publish
     │
     └── optional WinGet/mise metadata update
```

---

# 32. CLI Self-Update

Canonical Marpme installations must support:

```bash
marpme self update
```

## 32.1 Update availability checks

Marpme should automatically check whether a newer CLI release exists during normal use.

The check must not make normal commands noticeably slower.

Use a cached update record, for example:

```json
{
  "checked_at": "2026-08-26T14:00:00Z",
  "latest": "0.8.0"
}
```

Recommended default policy:

- refresh at most once every 24 hours,
- reuse cached result between checks,
- update-check failures must never break normal Marpme commands,
- never silently install updates.

If a newer version is known, print a brief notice after the normal command result:

```text
Marpme 0.8.0 is available.
Run `marpme self update` to upgrade.
```

## 32.2 Release manifest

Marpme should consume a small release manifest rather than tightly coupling itself to GitHub/GitLab API semantics.

Example:

```json
{
  "version": "0.8.0",
  "artifacts": {
    "windows-x86_64": {
      "url": "https://company.example/releases/marpme-windows-x86_64.exe",
      "sha256": "..."
    },
    "linux-x86_64": {
      "url": "https://company.example/releases/marpme-linux-x86_64",
      "sha256": "..."
    },
    "linux-aarch64": {
      "url": "https://company.example/releases/marpme-linux-aarch64",
      "sha256": "..."
    }
  }
}
```

The release manifest is the canonical source for self-update discovery.

## 32.3 Update process

`marpme self update` must:

1. perform a fresh release-manifest check,
2. compare semantic versions,
3. select the matching OS/architecture artifact,
4. download to a temporary location,
5. verify SHA-256,
6. preserve executable permissions where applicable,
7. replace the installed executable safely,
8. report the installed version.

Never update silently.

## 32.4 Windows replacement behavior

Because a running Windows executable cannot reliably overwrite itself, the implementation must use a safe replacement strategy.

Acceptable patterns include:

- spawn a small replacement process that waits for the current process to exit and then swaps the binary,
- use a temporary helper executable or locally generated helper script.

Routine self-update must not execute a newly downloaded remote script.

The downloaded Marpme artifact must be checksum-verified before replacement.

## 32.5 Linux replacement behavior

On Linux/WSL:

1. download replacement,
2. verify checksum,
3. mark executable,
4. atomically replace the installed binary where possible.

## 32.6 Ownership detection

Self-update is enabled only when Marpme owns the installation.

Canonical install-script installations are Marpme-owned.

Ephemeral npm/pnpm launchers are not.

If installation ownership cannot be established safely, do not overwrite files. Show an actionable message instead.

# 33. Stable vs Development Channels

Initial version may support only stable releases.

Future model:

```bash
marpme upgrade --channel stable
marpme upgrade --channel beta
```

Similarly for templates:

```yaml
template:
  channel: stable
```

Do not implement channels in v1 unless needed.

Design config so they can be added later.

---

# 34. Network Access

Creating or updating a Marpme environment may require access to the template source.

Requirements:

- clear timeout behavior,
- helpful network error,
- preserve existing repository on failure,
- never leave half-written state where avoidable.

Template source may be:

- internal Git repository,
- HTTPS Git repository,
- authenticated company Git service.

Authentication should rely on normal Git/user credential mechanisms where practical.

Do not store credentials in Marpme config.

---

# 35. Transactional Behavior

Operations should avoid partial mutation.

For multi-step operations:

1. validate prerequisites first,
2. perform template work,
3. perform repository integration,
4. only report success after all required steps succeed.

Where practical:

- stage temporary files,
- use atomic file replacement,
- preserve original files before structured merges.

Do not leave invalid JSON files after a failed editor integration.

---

# 36. Concurrency

Prevent simultaneous template mutations in the same repository.

Use a simple repository-level lock during mutating operations such as:

```text
marpme new
marpme update
```

Potential location:

```text
.marpme/.lock
```

The lock must be resilient to stale processes.

A basic advisory lock is sufficient.

---

# 37. Telemetry

No telemetry should be added by default.

If telemetry is ever introduced:

- it must be explicitly specified,
- privacy requirements must be reviewed,
- users must be informed.

Do not implement telemetry in v1.

---

# 38. Testing Strategy

## 41.1 Unit tests

Test:

- repository detection,
- deck-name validation,
- config parsing,
- VS Code JSON merging,
- version parsing,
- platform detection,
- error translation.

## 41.2 Integration tests

Create temporary Git repositories and test:

```text
new
new second deck
update
template change
local modification
Copier merge
VS Code file already exists
missing Git
existing target directory
```

## 41.3 Template upgrade tests

Maintain test fixtures:

```text
template-v1/
template-v2/
```

Test scenario:

1. generate project using v1,
2. modify generated file locally,
3. update template to v2,
4. run update,
5. assert Copier merge behavior.

This is a critical test suite.

## 41.4 Platform tests

CI must test at minimum:

- Windows x86_64,
- Linux x86_64.

Prefer also:

- Linux ARM64.

---

# 39. Packaging Tests

Each release binary must be smoke-tested.

Example CI commands:

```bash
marpme --version
marpme --help
marpme doctor
```

Also create a temporary repository and run:

```bash
marpme new smoke-test
```

The test should validate that the frozen binary contains Copier and all Python dependencies necessary for template operations.

---

# 40. Performance Requirements

This is not a high-frequency build tool.

Primary performance goals:

- startup should feel responsive,
- status should be fast,
- update performance may be dominated by Git/Copier,
- correctness is more important than micro-optimizing startup time.

A PyInstaller startup delay is acceptable if it remains in the normal range for an interactive CLI.

---

# 41. Compatibility

Support:

### Windows

- PowerShell 5.1+ where practical.
- PowerShell 7+.
- Windows 10/11 corporate developer environments.

### Linux

- common x86_64 developer distributions.
- WSL2 distributions.

Avoid dependencies on distribution-specific package managers.

---

# 42. Internal API Boundaries

The implementation should have explicit service boundaries.

Recommended:

```text
CLI layer
   │
   ├── RepositoryService
   ├── CopierService
   ├── VsCodeService
   ├── ReleaseService
   ├── ToolService
   └── ProcessService
```

The CLI command handlers should remain thin.

Example:

```python
@app.command()
def update():
    repo = repository_service.find()
    result = template_service.update(repo)
    renderer.show_update_result(result)
```

Avoid placing Git/Copier/file mutation logic directly in Typer command functions.

---

# 43. Data Models

Prefer typed dataclasses or Pydantic only if validation complexity justifies it.

Potential models:

```text
Repository
Deck
TemplateVersion
CliVersion
UpdateResult
DoctorResult
ReleaseArtifact
Platform
```

Do not introduce a large domain framework.

---

# 44. Configuration Parsing

Use YAML only where already natural for Copier / Marpme config.

Use JSON for VS Code files.

Preserve comments if modifying JSON-with-comments becomes necessary.

Important:

VS Code configuration may use JSONC, not strict JSON.

If modifying files that may contain comments:

- use a JSONC-capable parser,
- preserve structure/comments where feasible,
- do not rewrite files using plain `json.dumps()` if that destroys valid user configuration.

For `.vscode/extensions.json`, choose a library or implementation that handles JSONC correctly.

---

# 45. Template Source Configuration

The canonical template source should be configurable at build time or organization level.

Example default:

```text
https://git.company.example/dev-tools/marpme-template.git
```

Possible override for testing:

```bash
marpme new foo --template ./local-template
```

or environment variable:

```text
MARPME_TEMPLATE_SOURCE
```

A local-template override is valuable for development and integration tests.

Do not make normal users specify the source.

---

# 46. Environment Variables

Recommended initial environment variables:

```text
MARPME_TEMPLATE_SOURCE
MARPME_LOG_LEVEL
MARPME_CACHE_DIR
```

Optional later:

```text
MARPME_CHANNEL
```

Command-line arguments should override environment variables.

Repository config should override built-in defaults where appropriate.

Document precedence.

---

# 47. Cache

Use platform-appropriate cache locations.

Example:

Windows:

```text
%LOCALAPPDATA%\Marpme\cache
```

Linux:

```text
$XDG_CACHE_HOME/marpme
```

or:

```text
~/.cache/marpme
```

Potential cached data:

- CLI release metadata,
- last update-check timestamp,
- downloaded temporary artifacts,
- template metadata.

Do not place disposable global cache inside the user's repository.

---

# 48. Offline Behavior

If a repository already has the required template state, commands that do not require network access should continue to work offline.

`marpme status` should display locally known state even if checking latest version fails:

```text
Template 1.6.0
Latest   unknown (offline)
```

Creation/update may fail if the template source is unavailable and no suitable cache exists.

Do not claim successful freshness checks while offline.

---

# 49. Exit Codes

Use meaningful process exit codes.

Minimum:

```text
0  success
1  generic failure
2  invalid usage
```

Optionally define stable application codes later for automation.

Do not make human-facing behavior dependent on obscure exit codes.

---

# 50. Documentation Structure

Main README should optimize for immediate onboarding.

Suggested:

```text
# Marpme

Create:
  marpme new architecture-review

Install:
  Windows ...
  Python ...
  Linux/WSL ...

Update template:
  marpme update
```

Do not start the README with architecture details.

Detailed documentation can cover:

- installation variants,
- template authoring,
- upgrade model,
- internal architecture,
- troubleshooting.

---

# 51. Recommended Installation Documentation

Keep the installation story deliberately small.

## Windows — canonical

Fast path:

```powershell
irm https://company.example/marpme/install.ps1 | iex
```

Inspectable path:

```powershell
irm https://company.example/marpme/install.ps1 -OutFile install-marpme.ps1
.\install-marpme.ps1
```

After installation:

```powershell
marpme
```

## Linux / WSL — canonical

```bash
curl -fsSL https://company.example/marpme/install.sh | sh
```

After installation:

```bash
marpme
```

## Node ecosystem — zero-install convenience

```bash
npx @company/marpme
```

or:

```bash
pnpm dlx @company/marpme
```

These are ephemeral launch paths and do not provide persistent self-update ownership.

## Updating Marpme

Canonical installations notify users when an update is available:

```text
Marpme 0.8.0 is available.
Run `marpme self update` to upgrade.
```

Update with:

```bash
marpme self update
```

Do not document pip, pipx, uv, mise, WinGet, or global npm installation as primary installation mechanisms.

# 52. Dependency Philosophy

The end-user dependency model is:

```text
Canonical standalone usage:
  marpme binary
  Git

Optional:
  VS Code
```

Canonical users do not need Python, Node.js, pip, uv, mise, WinGet, or another package manager.

The implementation dependency model is:

```text
Python
Typer
Rich
Copier
supporting libraries
```

These Python dependencies are bundled into the standalone release.

The fact that the implementation is Python must not create a Python prerequisite for standalone users.

---

# 53. Why Python Instead of Rust

Python is intentionally selected because Copier is central to the product.

Benefits:

- direct Copier API integration,
- no embedded Python sidecar,
- no reimplementation of template merging,
- simple file/config orchestration,
- fast development,
- good CLI libraries,
- standalone binary still possible via PyInstaller.

Rust would be preferred only if the product were primarily:

- a compiler,
- a daemon,
- a high-performance filesystem engine,
- an extremely startup-sensitive binary.

That is not the primary workload of Marpme.

---

# 54. Why Copier Instead of Custom Sync

Do not replace Copier with custom logic such as:

```text
if managed:
    overwrite
else:
    preserve
```

The product explicitly requires template evolution with local user changes.

Copier is responsible for:

- template generation,
- recorded answers/state,
- version-aware updates,
- merge behavior,
- conflict surfacing.

Marpme should orchestrate Copier, not duplicate it.

---

# 55. Future Features

Architect for but do not necessarily implement:

- `marpme list`,
- `marpme remove`,
- `marpme rename`,
- template channels,
- multiple template flavors,
- presentation linting,
- CI validation,
- company brand validation,
- AI prompt invocation,
- VS Code extension,
- shell completion,
- repository-wide deck index,
- remote deck template catalog.

---

# 56. MVP Scope

The first useful release should include:

1. Python CLI project.
2. Typer commands.
3. Rich output.
4. Repository detection.
5. `marpme new`.
6. Copier integration.
7. repository-level template initialization.
8. creation of deck folder.
9. VS Code extension recommendation merge.
10. `marpme update`.
11. `marpme status`.
12. `marpme doctor`.
13. PyInstaller Windows build.
14. PyInstaller Linux x64 build.
15. PowerShell installer.
16. shell installer.
17. cached CLI update-availability checks.
18. `marpme self update` for canonical installations.
19. npm/npx wrapper.
20. pnpm compatibility through the npm package.
21. CI integration tests for Copier upgrades.

Can be deferred:

- self-update,
- ARM64,
- macOS.

---

# 57. Suggested Implementation Order

## Phase 1 — Core

Implement:

```text
repository detection
config
CopierService
new
update
status
doctor
```

Use local template fixtures first.

## Phase 2 — Real template repository

Connect to:

```text
company/marpme-template
```

Add version/tag handling.

## Phase 3 — Repository integration

Implement:

```text
VS Code extension recommendation
shared .marpme structure
deck creation
```

## Phase 4 — Packaging

Build:

```text
Windows executable
Linux executable
```

## Phase 5 — Distribution

Add:

```text
install.ps1
install.sh
self-update release manifest
npm wrapper
```

## Phase 6 — UX refinement

Add:

```text
better diagnostics
status
upgrade notifications
changelog summaries
shell completion
```

---

# 58. Acceptance Criteria

The implementation is considered successful when all of the following work.

## Scenario A — Windows user without Python

Given:

- Windows,
- PowerShell,
- Git,
- no Python,
- no Node,
- no mise.

User installs standalone Marpme.

Then:

```powershell
marpme new architecture-review
```

must create a valid presentation environment.

---

## Scenario B — WSL user

Given a WSL shell and Git:

```bash
marpme new architecture-review
```

must behave equivalently to Windows.

---

## Scenario C — Node user

Without permanent installation:

```bash
npx @company/marpme new architecture-review
```

must invoke the same Marpme implementation and produce equivalent scaffolding behavior.

Also:

```bash
pnpm dlx @company/marpme new architecture-review
```

must work.

These invocations are ephemeral. `marpme self update` must not modify npm/pnpm-managed cache contents.

---

## Scenario D — Self-update notification and update

Given a canonical Marpme installation with version `0.7.0` and a current release `0.8.0`:

A normal Marpme command should complete normally and may append:

```text
Marpme 0.8.0 is available.
Run `marpme self update` to upgrade.
```

Then:

```bash
marpme self update
```

must install the matching verified `0.8.0` artifact.

## Scenario E — Existing VS Code configuration

Given:

```json
{
  "recommendations": [
    "some.other-extension"
  ]
}
```

after Marpme initialization it must become logically equivalent to:

```json
{
  "recommendations": [
    "some.other-extension",
    "marp-team.marp-vscode"
  ]
}
```

without deleting the existing entry.

---

## Scenario F — Template update without local edits

Generate from template `1.0.0`.

Release template `1.1.0`.

Run:

```bash
marpme update
```

Result must match Copier's expected update result.

---

## Scenario G — Template update with local edits

Generate from template `1.0.0`.

Modify a generated/template-derived file locally.

Release template `1.1.0` modifying the same area.

Run:

```bash
marpme update
```

Marpme must delegate merge handling to Copier and surface resulting conflicts if automatic reconciliation is impossible.

No custom silent overwrite is allowed.

---

## Scenario H — Existing deck

Given:

```text
foo/
```

then:

```bash
marpme new foo
```

must fail safely without overwriting the existing deck.

---

## Scenario I — Offline status

Given an already initialized repository and no network:

```bash
marpme status
```

must still report local CLI/template/deck state and explicitly state that remote freshness could not be checked.

---

## Scenario J — Bare command shortcut

Given an existing Git repository:

```bash
marpme
```

must behave exactly like:

```bash
marpme new slidedeck
```

and create:

```text
slidedeck/
```

If that deck already exists, the command must fail safely and must not overwrite it.

---

# 59. Definition of Done for v1

v1 is done when:

- users no longer need to clone the template repository,
- users do not need submodules,
- users can initialize a deck with one command,
- template updates work through Copier,
- local template modifications are not silently discarded,
- users can install without Python or a package manager,
- Windows and Linux/WSL binaries exist,
- PowerShell and shell bootstrap installers exist,
- canonical installations support update notifications and `marpme self update`,
- npx and pnpm ephemeral invocation exist,
- VS Code recommendations are merged safely,
- implementation is covered by integration tests,
- template version information is visible,
- error output is actionable.

---

# 60. Guiding Product Principle

The user experience should feel like:

```text
"Add the company presentation environment to this repo"
```

not like:

```text
"Clone and maintain another template repository."
```

The abstraction exposed to the user is:

```bash
marpme                  # shortcut for: marpme new slidedeck
marpme new <name>
marpme update
marpme status
```

The implementation details:

```text
Copier
Python
Git
PyInstaller
npm wrapper
```

must remain mostly invisible.

---

# 61. Guiding Architecture Principle

**One implementation, one canonical owned lifecycle, optional ephemeral frontends.**

```text
                         marpme
                    Python application
                           │
                       PyInstaller
                           │
                    release binaries
                           │
              ┌────────────┴────────────┐
              │                         │
         install.ps1                install.sh
           Windows                  Linux / WSL
              │                         │
              └────────────┬────────────┘
                           │
                    Marpme-owned install
                           │
                    marpme self update

Optional zero-install access:

  npx @company/marpme
  pnpm dlx @company/marpme
```

Do not create parallel implementations for different ecosystems.

Do not let third-party package managers own the primary lifecycle if that would prevent reliable Marpme-controlled self-update.

# 62. Final Implementation Direction

Build `marpme` as:

```text
Python + Typer + Rich + Copier
```

Develop with:

```text
uv + pytest + ruff
```

Package standalone releases with:

```text
PyInstaller
```

Canonical distribution:

```text
PowerShell install script
shell install script
direct release binaries
```

Optional zero-install convenience:

```text
npm / npx / pnpm launcher
```

Canonical installations must:

```text
check periodically for CLI updates
notify without blocking normal work
update explicitly through `marpme self update`
```

Do not make pip, pipx, uv, mise, WinGet, or global npm installation part of the primary lifecycle.

Use:

```text
Git-tagged Copier template repository
```

as the canonical source for:

```text
Marp template
CSS/theme
AI skill
helper scripts
repository configuration
```

The single most important architectural constraint is:

> **Do not reimplement Copier's template-update and merge semantics. Treat Copier as the template lifecycle engine and Marpme as the product-facing orchestration layer.**
