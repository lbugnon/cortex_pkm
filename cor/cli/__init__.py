"""Cortex CLI - Command modules.

This package contains the CLI command implementations, organized by category:
- init: Vault initialization commands
- notes: Note/task management commands  
- config: Configuration and settings commands
- maintenance: Sync, hooks, and maintenance commands
"""

import os
import subprocess
from pathlib import Path

import click

from .. import __version__
from ..config import get_verbosity, set_verbosity


HOOKS_DIR = Path(__file__).parent.parent / "hooks"


@click.group(context_settings={
    "help_option_names": ["-h", "--help"],
    "max_content_width": 100,
})
@click.version_option(__version__, prog_name="CortexPKM")
@click.option(
    "--verbose", "-v",
    count=True,
    help="Increase verbosity level (can be used multiple times: -v, -vv, -vvv)"
)
@click.pass_context
def cli(ctx, verbose: int):
    """Cortex - Plain text knowledge management.
    
    A lightweight tool for managing projects, tasks, and notes using
    plain text files and git. 
    """
    if verbose > 0:
        current_level = get_verbosity()
        new_level = min(current_level + verbose, 3)
        set_verbosity(new_level)


def _install_pre_commit_hook() -> None:
    """Install the pre-commit git hook."""
    import shutil
    import stat
    
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise click.ClickException("Not in a git repository.")

    git_dir = Path(result.stdout.strip())
    hooks_target = git_dir / "hooks"
    hooks_target.mkdir(exist_ok=True)

    source = HOOKS_DIR / "pre-commit"
    target = hooks_target / "pre-commit"

    if not source.exists():
        raise click.ClickException(f"Hook source not found: {source}")

    if target.exists():
        click.echo(f"Overwriting existing {target}")

    shutil.copy(source, target)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    click.echo(f"Installed pre-commit hook to {target}")


def _install_shell_completion() -> None:
    """Install shell completion based on detected shell."""
    shell = os.environ.get("SHELL", "")
    
    if "zsh" in shell:
        _install_zsh_completion()
    elif "bash" in shell:
        _install_bash_completion()
    else:
        click.echo("Shell not detected. For shell completion, add to your shell config:")
        click.echo('  # For zsh: eval "$(_COR_COMPLETE=zsh_source cor)"')
        click.echo('  # For bash: eval "$(_COR_COMPLETE=bash_source cor)"')


def _install_zsh_completion():
    """Install completion for zsh by updating ~/.zshrc."""
    zshrc = Path.home() / ".zshrc"
    
    completion_block = '''
# Cortex shell completion
if command -v cor &> /dev/null; then
    setopt MENU_COMPLETE

    _cor_completion() {
        local -a completions completions_partial
        local -a response
        (( ! $+commands[cor] )) && return 1

        response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _COR_COMPLETE=zsh_complete cor)}")

        local i=1
        local rlen=${#response}
        while (( i <= rlen )); do
            local type=${response[i]}
            local key=${response[i+1]:-}
            local descr=${response[i+2]:-}
            (( i += 3 ))
            if [[ "$type" == "plain" && -n "$key" ]]; then
                if [[ "$key" == *. ]]; then
                    completions_partial+=("$key")
                else
                    completions+=("$key")
                fi
            fi
        done

        if [[ ${#completions_partial} -eq 0 && ${#completions} -eq 0 ]]; then
            return 1
        fi

        if [[ ${#completions_partial} -gt 0 ]]; then
            compadd -Q -U -S '' -V partial -- ${completions_partial[@]}
        fi
        if [[ ${#completions} -gt 0 ]]; then
            compadd -Q -U -V unsorted -- ${completions[@]}
        fi
    }
    compdef _cor_completion cor
fi
'''
    
    if zshrc.exists():
        content = zshrc.read_text()
        if "# Cortex shell completion" in content or "_cor_completion" in content:
            click.echo("Shell completion already configured in ~/.zshrc")
            return
    
    with zshrc.open("a") as f:
        f.write(completion_block)
    
    click.echo("Added shell completion to ~/.zshrc")
    click.echo("Run 'source ~/.zshrc' or restart your shell to enable")


def _install_bash_completion():
    """Install completion for bash by updating ~/.bashrc."""
    bashrc = Path.home() / ".bashrc"
    
    completion_block = '''
# Cortex shell completion
if command -v cor &> /dev/null; then
    eval "$(_COR_COMPLETE=bash_source cor)"
fi
'''
    
    if bashrc.exists():
        content = bashrc.read_text()
        if "# Cortex shell completion" in content or "_COR_COMPLETE=bash_source" in content:
            click.echo("Shell completion already configured in ~/.bashrc")
            return
    
    with bashrc.open("a") as f:
        f.write(completion_block)
    
    click.echo("Added shell completion to ~/.bashrc")
    click.echo("Run 'source ~/.bashrc' or restart your shell to enable")


def _uninstall_pre_commit_hook() -> None:
    """Remove cortex git hooks."""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise click.ClickException("Not in a git repository.")

    git_dir = Path(result.stdout.strip())
    target = git_dir / "hooks" / "pre-commit"

    if target.exists():
        target.unlink()
        click.echo(f"Removed {target}")
    else:
        click.echo("No pre-commit hook found.")


# Import and register all commands
from .init import init, example_vault
from .config import config_cmd, focus, inbox_cmd
from .notes import new, edit, tag, delete, mark, expand
from .maintenance import sync, maintenance, hooks
from ..commands.refactor import rename, group
from ..commands.process import process
from ..commands.log import log
from ..commands.dependencies import depend
from ..commands.refs import ref
from ..commands.status import daily, projects, weekly, tree, status
from ..commands.calendar import auth as calendar_auth
from ..commands.calendar import sync as calendar_sync
from ..commands.calendar import status as calendar_status
from ..commands.calendar import logout as calendar_logout

cli.add_command(init)
cli.add_command(example_vault)
cli.add_command(config_cmd)
cli.add_command(focus)
cli.add_command(inbox_cmd)
cli.add_command(new)
cli.add_command(edit)
cli.add_command(tag)
cli.add_command(delete)
cli.add_command(delete, name="del")  # Alias
cli.add_command(mark)
cli.add_command(expand)
cli.add_command(sync)
cli.add_command(maintenance)
cli.add_command(hooks)
cli.add_command(rename)
cli.add_command(rename, name="move")  # Alias
cli.add_command(group)
cli.add_command(process)
cli.add_command(log)
cli.add_command(depend)
cli.add_command(ref)
cli.add_command(daily)
cli.add_command(projects)
cli.add_command(weekly)
cli.add_command(tree)
cli.add_command(status)

# Calendar commands group
@cli.group(name="calendar")
def calendar_group():
    """Google Calendar integration for due dates."""
    pass

calendar_group.add_command(calendar_auth, name="auth")
calendar_group.add_command(calendar_sync, name="sync")
calendar_group.add_command(calendar_status, name="status")
calendar_group.add_command(calendar_logout, name="logout")
cli.add_command(calendar_group)

__all__ = ["cli"]
