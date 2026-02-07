"""Configuration commands for Cortex CLI."""

import os
from pathlib import Path

import click

from . import cli
from ..config import (
    load_config,
    config_file,
    set_vault_path,
    get_verbosity,
    set_verbosity,
    get_focused_project,
    set_focused_project,
    clear_focused_project,
    get_remote_inbox,
    set_remote_inbox,
)
from ..utils import get_notes_dir, require_init


@cli.command(name="config")
@click.argument("key", type=click.Choice(["verbosity", "vault", "inbox"]), required=False)
@click.argument("value", required=False)
def config_cmd(key: str | None, value: str | None):
    """Manage CortexPKM configuration.

    View or modify global settings for verbosity, vault location, and remote inbox.

    \b
    Configuration Keys:
      verbosity    Output detail level (0=silent, 1=normal, 2=verbose, 3=debug)
      vault        Path to your notes directory
      inbox        Telegram bot token for mobile inbox

    \b
    Examples:
      cor config                      Show all settings
      cor config verbosity 2          Set verbose output
      cor config vault ~/my-notes     Change vault location
      cor config inbox <bot-token>    Configure Telegram inbox
    """
    # Show all config if no key provided
    if key is None:
        config_data = load_config()
        click.echo(click.style("Cortex Configuration", bold=True))
        click.echo(config_data)
        click.echo()
        
        return

    if key == "verbosity":
        if value is None:
            # Show current value
            current = get_verbosity()
            click.echo(f"Verbosity level: {current}")
            click.echo("Levels: 0=silent, 1=normal, 2=verbose, 3=debug")
        else:
            # Set new value
            try:
                level = int(value)
                if not 0 <= level <= 3:
                    raise ValueError()
                set_verbosity(level)
                click.echo(f"Verbosity set to {level}")
            except ValueError:
                raise click.ClickException(f"Invalid verbosity level: {value}. Must be 0-3.")

    elif key == "vault":
        if value is None:
            # Show current vault configuration
            notes_dir = get_notes_dir()
            config_data = load_config()
            env_vault = os.environ.get("CORTEX_VAULT")

            click.echo(click.style("Vault Configuration", bold=True))
            click.echo()

            if env_vault:
                click.echo(f"CORTEX_VAULT env: {env_vault} " + click.style("(active)", fg="green"))
            if config_data.get("vault"):
                status = "(active)" if not env_vault else "(overridden)"
                click.echo(f"Config file: {config_data['vault']} " + click.style(status, fg="yellow" if env_vault else "green"))
            if not env_vault and not config_data.get("vault"):
                click.echo(f"Current directory: {Path.cwd()} " + click.style("(active)", fg="green"))

            click.echo()
            click.echo(f"Active vault: {click.style(str(notes_dir), fg='cyan', bold=True)}")
            if (notes_dir / "root.md").exists():
                click.echo(click.style("  (initialized)", fg="green"))
            else:
                click.echo(click.style("  (not initialized - run 'cor init')", fg="yellow"))
        else:
            # Set vault path
            path = Path(value).expanduser().resolve()
            if not path.exists():
                raise click.ClickException(f"Path does not exist: {path}")
            if not path.is_dir():
                raise click.ClickException(f"Path is not a directory: {path}")
            set_vault_path(path)
            click.echo(f"Vault path set to: {path}")
            click.echo(f"Config saved to: {config_file()}")

    elif key == "inbox":
        if value is None:
            # Show current inbox configuration
            bot_token = get_remote_inbox()
            env_token = os.environ.get("TELEGRAM_BOT_TOKEN")

            click.echo(click.style("Remote Inbox Configuration", bold=True))
            click.echo()

            if env_token:
                click.echo("TELEGRAM_BOT_TOKEN env: " + click.style("(configured)", fg="green"))

            config_data = load_config()
            if config_data.get("remote_inbox"):
                status = "(active)" if not env_token else "(overridden)"
                masked = config_data['remote_inbox'][:8] + "..." if len(config_data['remote_inbox']) > 8 else "***"
                click.echo(f"Config file: {masked} " + click.style(status, fg="yellow" if env_token else "green"))

            if bot_token:
                click.echo()
                click.echo(click.style("Remote inbox is configured", fg="green"))
                click.echo("Send messages to your Telegram bot to capture them in backlog")
            else:
                click.echo()
                click.echo(click.style("Remote inbox not configured", fg="yellow"))
                click.echo("To setup: Create a bot via @BotFather, then run:")
                click.echo("  cor config inbox <bot-token>")
        else:
            # Set bot token
            set_remote_inbox(value)
            click.echo(click.style("Remote inbox configured", fg="green"))
            click.echo(f"Config saved to: {config_file()}")
            click.echo()
            click.echo("Messages sent to your Telegram bot will be pulled during 'cor sync'")


@cli.command()
@click.argument("project", required=False)
@require_init
def focus(project: str | None):
    """Set or show the focused project.

    When a project is focused, 'cor new', 'cor edit', and other commands
    will default to that project. This simplifies working on a single
    project without typing the full name each time.

    \b
    Examples:
      cor focus              # Show current focus
      cor focus myproject    # Focus on myproject
      cor focus off          # Clear focus
    """
    notes_dir = get_notes_dir()
    
    # Show current focus if no argument provided
    if project is None:
        focused = get_focused_project()
        if focused:
            click.echo(click.style(f"Focusing on: {focused}", fg="cyan", bold=True))
            click.echo(f"Run 'cor focus off' to clear")
        else:
            click.echo("No project focused. Run 'cor focus <project>' to set one.")
        return
    
    # Clear focus
    if project.lower() == "off":
        clear_focused_project()
        click.echo(click.style("Focus cleared.", fg="green"))
        return
    
    # Validate project exists
    from ..search import resolve_file_fuzzy
    
    # Try to find the project (projects have no dots in name)
    project_path = notes_dir / f"{project}.md"
    if not project_path.exists():
        # Try fuzzy matching
        result = resolve_file_fuzzy(project, include_archived=False)
        if result is None:
            raise click.ClickException(f"Project not found: {project}")
        stem, _ = result
        # Check it's actually a project (no dots)
        if "." in stem:
            raise click.ClickException(
                f"'{stem}' is not a project. Can only focus on top-level projects."
            )
        project = stem
    
    # Set focus
    set_focused_project(project)
    click.echo(click.style(f"Focusing on: {project}", fg="green", bold=True))
    click.echo("Commands like 'cor new', 'cor edit' will default to this project.")


@cli.command(name="inbox")
def inbox_cmd():
    """Test remote inbox connection.

    Checks if the Telegram bot is configured and shows pending messages.
    """
    from ..commands.inbox import test_telegram_connection

    bot_token = get_remote_inbox()
    if not bot_token:
        click.echo(click.style("Remote inbox not configured", fg="yellow"))
        click.echo("Run: cor config inbox <bot-token>")
        return

    test_telegram_connection(bot_token)
