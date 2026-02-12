"""Maintenance, sync, and refactoring commands for Cortex CLI."""

import os
import subprocess
from datetime import datetime
from pathlib import Path

import click

from . import cli, _install_pre_commit_hook, _install_shell_completion, _uninstall_pre_commit_hook
from ..completions import complete_existing_name
from ..utils import get_notes_dir, require_init, log_info
from ..sync import MaintenanceRunner


@cli.command()
@click.option("--message", "-m", type=str, help="Custom commit message")
@click.option("--no-push", is_flag=True, help="Commit only, don't push")
@click.option("--no-pull", is_flag=True, help="Skip pull before commit")
@require_init
def sync(message: str | None, no_push: bool, no_pull: bool):
    """Sync vault with git remote.

    Convenient workflow: pull → commit all changes → push
    Auto-generates commit message based on changes.

    \b
    Examples:
      cor sync                        # Full sync
      cor sync -m "Add new tasks"     # With custom message
      cor sync --no-push              # Local commit only
    """
    notes_dir = get_notes_dir()

    os.chdir(notes_dir)
    # Check if we're in a git repo
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise click.ClickException("Not in a git repository.")

    # Step 0: Pull remote inbox (if configured)
    from ..config import get_remote_inbox
    from ..commands.inbox import pull_remote_inbox

    bot_token = get_remote_inbox()
    if bot_token:
        try:
            added = pull_remote_inbox(notes_dir, bot_token)
            if added:
                click.echo(click.style(f"Pulled {added} items from Telegram inbox", fg="cyan"))
        except click.ClickException as e:
            # Non-fatal: continue with git sync even if inbox pull fails
            click.echo(click.style(f"Inbox pull failed: {e.message}", fg="yellow"), err=True)

    # Sync calendar (if authenticated)
    from ..commands.calendar import _get_credentials
    if _get_credentials():
        try:
            from ..commands.calendar import sync as calendar_sync_cmd
            # Create a new context for the calendar sync command
            ctx = click.get_current_context()
            ctx.invoke(calendar_sync_cmd, calendar="Cortex Tasks")
        except Exception as e:
            # Non-fatal: continue with git sync even if calendar sync fails
            click.echo(click.style(f"Calendar sync failed: {e}", fg="yellow"), err=True)

    # Step 1: Pull (unless skipped)
    if not no_pull:
        click.echo("Pulling from remote...")
        result = subprocess.run(
            ["git", "pull"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            if "no tracking information" in result.stderr:
                click.echo(click.style("No remote tracking branch. Skipping pull.", dim=True))
            else:
                raise click.ClickException(f"Pull failed: {result.stderr}")
        elif result.stdout.strip():
            click.echo(result.stdout.strip())

    # Step 2: Check for changes
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True
    )
    changes = result.stdout.strip()

    if not changes:
        click.echo(click.style("No changes to commit.", fg="green"))
        return

    # Show what will be committed
    click.echo("\nChanges to commit:")
    for line in changes.split("\n"):
        status_char = line[:2].strip()
        filename = line[2:]
        if status_char == "M":
            click.echo(f"  {click.style('modified:', fg='yellow')} {filename}")
        elif status_char == "A":
            click.echo(f"  {click.style('added:', fg='green')} {filename}")
        elif status_char == "D":
            click.echo(f"  {click.style('deleted:', fg='red')} {filename}")
        elif status_char == "?":
            click.echo(f"  {click.style('untracked:', fg='cyan')} {filename}")
        else:
            click.echo(f"  {status_char} {filename}")

    # Step 3: Stage all changes
    subprocess.run(["git", "add", "-A"], check=True)

    # Step 4: Commit
    if not message:
        # Auto-generate commit message
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        message = f"Vault sync {now}"

    click.echo(f"\nCommitting: {message}")
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise click.ClickException(f"Commit failed: {result.stderr}")

    # Step 5: Push (unless skipped)
    if not no_push:
        click.echo("Pushing to remote...")
        result = subprocess.run(
            ["git", "push"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            if "no upstream branch" in result.stderr:
                click.echo(click.style("No upstream branch. Use 'git push -u origin <branch>' first.", fg="yellow"))
            else:
                raise click.ClickException(f"Push failed: {result.stderr}")
        else:
            click.echo(click.style("Synced!", fg="green"))
    else:
        click.echo(click.style("Committed (not pushed).", fg="green"))
    os.chdir("..")  # Return to previous directory


@cli.group()
def maintenance():
    """Maintenance operations for the vault.

    Run maintenance tasks like syncing archive/unarchive,
    updating checkboxes, and sorting tasks.
    """
    pass


@maintenance.command("sync")
@click.option("--all", "-a", "sync_all", is_flag=True, help="Sync all files, not just modified")
@require_init
def maintenance_sync(sync_all: bool):
    """Synchronize vault state: archive, status, checkboxes, sorting.

    By default, syncs files that have been modified according to git.
    Use --all to sync the entire vault.

    Examples:
        cor maintenance sync              # Sync git-modified files
        cor maintenance sync --all        # Sync everything
    """
    notes_dir = get_notes_dir()

    # Get files to sync
    if sync_all:
        files = [str(p) for p in notes_dir.glob("*.md") if p.stem not in ("root", "backlog")]
        archive_dir = notes_dir / "archive"
        if archive_dir.exists():
            files += [str(p) for p in archive_dir.glob("*.md")]
    else:
        # Get git-modified files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True
        )
        files = [f for f in result.stdout.strip().split("\n")
                 if f.endswith(".md") and not f.startswith("templates/") and f]

    if not files:
        click.echo("No files to sync.")
        return

    runner = MaintenanceRunner(notes_dir)
    result = runner.sync(files)

    # Check for errors
    if result.errors:
        click.echo(click.style("Validation errors:", fg="red"))
        for filepath, errors in result.errors.items():
            click.echo(f"\n  {filepath}:")
            for error in errors:
                click.echo(f"    - {error}")
        return

    # Report results
    changes = False

    if result.modified_dates_updated:
        changes = True
        click.echo(click.style("Modified dates updated:", fg="cyan"))
        for f in result.modified_dates_updated:
            click.echo(f"  {f}")

    if result.archived:
        changes = True
        click.echo(click.style("Archived:", fg="cyan"))
        for old, new in result.archived:
            click.echo(f"  {old} -> {new}")

    if result.unarchived:
        changes = True
        click.echo(click.style("Unarchived:", fg="cyan"))
        for old, new in result.unarchived:
            click.echo(f"  {old} -> {new}")

    if result.links_updated:
        changes = True
        click.echo(click.style("Links updated:", fg="cyan"))
        for f in result.links_updated:
            click.echo(f"  {f}")

    if result.group_status_updated:
        changes = True
        click.echo(click.style("Group status updated:", fg="cyan"))
        for f in result.group_status_updated:
            click.echo(f"  {f}")

    if result.checkbox_synced:
        changes = True
        click.echo(click.style("Checkboxes synced:", fg="cyan"))
        for f in result.checkbox_synced:
            click.echo(f"  {f}")

    if result.tasks_sorted:
        changes = True
        click.echo(click.style("Tasks sorted:", fg="cyan"))
        for f in result.tasks_sorted:
            click.echo(f"  {f}")

    if result.deleted_links_removed:
        changes = True
        click.echo(click.style("Deleted task links removed:", fg="cyan"))
        for f in result.deleted_links_removed:
            click.echo(f"  {f}")

    if not changes:
        click.echo(click.style("No changes needed.", fg="green"))
    else:
        click.echo(click.style("\nDone!", fg="green"))


@cli.group()
def hooks():
    """Manage git hooks and shell completion.
    
    Git hooks automatically update file metadata on commits.
    """
    pass


@hooks.command("install")
def hooks_install():
    """Install git hooks and shell completion.

    \b
    Installs:
      • Pre-commit hook - Auto-updates 'modified' dates
      • Shell completion - Tab complete for file names
    
    Automatically runs during 'cor init' if in a git repo.
    """
    _install_pre_commit_hook()
    _install_shell_completion()


@hooks.command("uninstall")
def hooks_uninstall():
    """Remove cortex git hooks."""
    _uninstall_pre_commit_hook()


# rename command is defined in commands.refactor module and registered via register_additional_commands()


# Note: Additional commands from commands/ modules are registered in cli/__init__.py
# to avoid circular imports. See _register_commands() in __init__.py
