from __future__ import annotations

import sys
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Annotated

import click
import typer
from packaging.version import InvalidVersion, Version
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from marpme import __version__
from marpme.commands.doctor import run_doctor
from marpme.commands.new import create_deck
from marpme.commands.status import get_status
from marpme.commands.update import update_environment
from marpme.errors import MarpmeError
from marpme.services.releases import ReleaseService


class DefaultCommandGroup(TyperGroup):
    """Make `marpme` and `marpme <name>` aliases for `new`."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if not args:
            args.insert(0, "slidedeck")
            args.insert(0, "new")
        return super().parse_args(ctx, args)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        # Click has consumed group options by this point, so this also handles
        # `marpme --verbose deck-name` correctly.
        if args and not args[0].startswith("-") and args[0] not in self.commands:
            args.insert(0, "new")
        return super().resolve_command(ctx, args)


app = typer.Typer(
    cls=DefaultCommandGroup,
    name="marpme",
    help="Create and maintain Marp presentation environments.",
    no_args_is_help=False,
    pretty_exceptions_enable=False,
    add_completion=False,
)
self_app = typer.Typer(help="Manage the installed marpme CLI.")
app.add_typer(self_app, name="self")
console = Console()
error_console = Console(stderr=True)
_verbose = False
_check_updates = True


@contextmanager
def _activity(initial: str) -> Iterator[Callable[[str], None]]:
    """Show a live spinner in terminals and durable stage lines in logs."""
    if console.is_terminal:
        with console.status(initial, spinner="dots") as status:
            yield lambda message: status.update(message)
        return
    console.print(initial)

    def report(message: str) -> None:
        console.print(message)

    yield report


@app.callback(invoke_without_command=True)
def main_options(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show detailed diagnostics.")
    ] = False,
    check_updates: Annotated[
        bool,
        typer.Option(
            "--check-updates/--no-update-check",
            help="Check the cached CLI release information after commands.",
        ),
    ] = True,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the installed version.", is_eager=True),
    ] = False,
) -> None:
    global _verbose, _check_updates
    _verbose = verbose
    _check_updates = check_updates
    if version:
        console.print(f"marpme {__version__}")
        raise typer.Exit()


def _failure(exc: Exception) -> None:
    if _verbose and not isinstance(exc, MarpmeError):
        traceback.print_exc()
    error_console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(code=1) from exc


def _update_notice() -> None:
    if not _check_updates:
        return
    try:
        with _activity("Checking for marpme updates..."):
            latest = ReleaseService().available_update()
    except Exception:
        return
    if latest:
        console.print()
        console.print(f"[yellow]marpme {latest} is available.[/yellow]")
        console.print("Run [bold]marpme self update[/bold] to upgrade.")


@app.command("new")
def new_command(
    name: Annotated[str, typer.Argument(help="Safe folder name for the presentation.")],
    template: Annotated[
        str | None,
        typer.Option("--template", help="Override the Copier template source."),
    ] = None,
    template_ref: Annotated[
        str | None,
        typer.Option("--template-ref", help="Use a specific template tag or Git ref."),
    ] = None,
) -> None:
    """Create a new presentation in the current repository."""
    try:
        console.print(f'Creating presentation [bold]"{name}"[/bold]')
        with _activity("Detecting Git repository...") as progress:
            deck_file, template_version, vscode_changed = create_deck(
                name, source=template, vcs_ref=template_ref, progress=progress
            )
    except Exception as exc:
        _failure(exc)
    console.print("[green]✓[/green] Repository detected")
    console.print(f"[green]✓[/green] Template {template_version or 'version not recorded'} applied")
    console.print(f"[green]✓[/green] Presentation created: {deck_file.parent.as_posix()}")
    if vscode_changed:
        console.print("[green]✓[/green] VS Code configuration merged")
    console.print("\nNext:")
    console.print(f"  edit {deck_file.as_posix()}")
    _update_notice()


@app.command("update")
def update_command(
    to: Annotated[
        str | None, typer.Option("--to", help="Template tag/version, or 'latest'.")
    ] = None,
) -> None:
    """Apply a newer repository template using Copier."""
    try:
        with _activity("Checking repository and template state...") as progress:
            result = update_environment(to, progress=progress)
    except Exception as exc:
        _failure(exc)
    console.print(f"Current template: {result.previous_version or 'unknown'}")
    console.print(f"Updated template: {result.current_version or 'unknown'}")
    if result.changes:
        console.print("\nChanges:")
        for change in result.changes:
            console.print(f"  - {change}")
    if result.conflicts:
        console.print("\n[yellow]! Template update completed with conflicts[/yellow]\n")
        console.print("Conflicts:")
        for conflict in result.conflicts:
            console.print(f"  {conflict.as_posix()}")
        console.print("\nResolve the conflict markers, then commit the result.")
        raise typer.Exit(code=1)
    if result.configuration_conflicts:
        console.print("\n[yellow]! VS Code configuration has conflicts[/yellow]\n")
        console.print("User values were preserved in:")
        for conflict in result.configuration_conflicts:
            console.print(f"  {conflict.as_posix()}")
        console.print("\nThe template changed the same entries. Review and commit the result.")
        raise typer.Exit(code=1)
    console.print("\n[green]✓[/green] Copier update completed")
    _update_notice()


@app.command("status")
def status_command(
    offline: Annotated[
        bool, typer.Option("--offline", help="Do not query the template Git source.")
    ] = False,
) -> None:
    """Show local template and deck state."""
    try:
        with _activity("Reading marpme repository status...") as progress:
            status = get_status(check_remote=not offline, progress=progress)
    except Exception as exc:
        _failure(exc)
    table = Table(title="marpme", box=None, show_header=False, padding=(0, 2))
    table.add_row("CLI", status.cli_version)
    table.add_row("Template", status.template_version or "unknown")
    table.add_row("Latest", status.latest_version or "unknown (offline or unavailable)")
    console.print(table)
    console.print("\n[bold]Decks[/bold]")
    if status.decks:
        for deck in status.decks:
            console.print(f"  {deck}")
    else:
        console.print("  none")
    if status.latest_version and status.template_version:
        try:
            if Version(status.latest_version) > Version(status.template_version):
                console.print("\n[yellow]Template update available.[/yellow]")
        except InvalidVersion:
            pass
    _update_notice()


@app.command("doctor")
def doctor_command(
    offline: Annotated[
        bool, typer.Option("--offline", help="Skip template-source connectivity.")
    ] = False,
) -> None:
    """Check prerequisites and repository integration."""
    try:
        checks = run_doctor(check_remote=not offline)
    except Exception as exc:
        _failure(exc)
    console.print("[bold]marpme doctor[/bold]\n")
    failed = False
    for check in checks:
        marker = "[green]✓[/green]" if check.ok else "[red]✗[/red]"
        failed |= not check.ok
        detail = f" — {check.detail}" if check.detail else ""
        console.print(f"{marker} {check.name}{detail}")
    if failed:
        raise typer.Exit(code=1)
    _update_notice()


@self_app.command("update")
def self_update_command() -> None:
    """Update a canonical marpme installation."""
    # Resolve terminal styling before the executable update is scheduled. A
    # one-file PyInstaller archive must not be accessed through Rich afterward.
    success = "\033[32m✓\033[0m" if console.is_terminal else "✓"
    try:
        version = ReleaseService().self_update()
    except Exception as exc:
        _failure(exc)
    if version == __version__:
        sys.stdout.write(f"{success} marpme {version} is already current.\n")
    else:
        # Do not render with Rich after scheduling replacement: one-file PyInstaller
        # builds may lazily import from their archive, which is about to be replaced.
        sys.stdout.write(f"{success} marpme update completed: {version}\n")
        sys.stdout.flush()
