"""Cortex CLI - Plain text knowledge management."""

import os
import re
import shutil
import stat
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import click
import frontmatter

from . import __version__
from .commands import daily, projects, weekly, tree, review, rename, group, process
from .completions import complete_name, complete_task_name, complete_task_status, complete_existing_name
from .config import set_vault_path, load_config, config_file, set_verbosity, get_verbosity
from .maintenance import MaintenanceRunner
from .parser import parse_note
from .schema import STATUS_SYMBOLS, VALID_TASK_STATUS, DATE_TIME
from .utils import (
    get_notes_dir,
    get_templates_dir,
    get_template,
    format_title,
    render_template,
    open_in_editor,
    add_task_to_project,
    require_init,
    log_info,
    log_verbose,
)

HOOKS_DIR = Path(__file__).parent / "hooks"


@click.group(context_settings={
    "help_option_names": ["-h", "--help"],
    "max_content_width": 100,
})
@click.version_option(__version__, prog_name="cor")
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
    # Set verbosity level (0-3)
    # Each -v increases verbosity by 1, starting from default level in config
    if verbose > 0:
        current_level = get_verbosity()
        new_level = min(current_level + verbose, 3)
        set_verbosity(new_level)



@cli.command()
@click.pass_context
@click.option("yes", "--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompts")
def init(ctx, yes: bool):
    """Initialize a new Cortex vault.
    
    Creates the necessary directory structure and template files.
    Sets this directory as your vault path in the global config.
    Automatically installs git hooks if in a git repository.
    
    Run 'git init' first if you want automatic date tracking.
    """
    # Ask for confirmation to set this directory as vault
    vault_path = Path.cwd()
    log_info(f"Initializing Cortex vault in: {vault_path}")
    if not yes:
        if not click.confirm("Continue?", default=True):
            click.echo("Aborted.")
            return
    set_vault_path(vault_path)
    
    # Get directories AFTER setting vault path
    notes_dir = get_notes_dir()
    templates_dir = get_templates_dir()

    # Create directories
    notes_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)

    # Create root.md
    root_path = notes_dir / "root.md"
    if not root_path.exists():
        root_template = (Path(__file__).parent / "assets" / "root.md").read_text()
        now = datetime.now().strftime(DATE_TIME)
        root_path.write_text(root_template.format(date=now))
        log_verbose(f"Created {root_path}")

    # Create backlog.md
    backlog_path = notes_dir / "backlog.md"
    if not backlog_path.exists():
        backlog_template = (Path(__file__).parent / "assets" / "backlog.md").read_text()
        now = datetime.now().strftime(DATE_TIME)
        backlog_path.write_text(backlog_template.format(date=now))
        log_verbose(f"Created {backlog_path}")

    # Create default templates
    assets_dir = Path(__file__).parent / "assets"
    for filename in ["project.md", "task.md", "note.md"]:
        path = templates_dir / filename
        if not path.exists():
            content = (assets_dir / filename).read_text()
            path.write_text(content)
            log_verbose(f"Created {path}")

    log_info("Cortex vault initialized.")

    # Install git hooks if in a git repository
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        ctx.invoke(hooks_install)
    else:
        log_verbose("Not in a git repository - skipping hook installation.")


@cli.command()
@click.pass_context
def example_vault(ctx):
    """Create a comprehensive example vault to demonstrate CortexPKM features.
    
    This command will create a sample vault with:
    - Multiple projects with different statuses
    - Tasks with various statuses (todo, active, done, blocked, waiting, dropped)
    - Task groups (hierarchical organization)
    - Notes under projects
    - Standalone notes
    
    Perfect for exploring CortexPKM capabilities and learning the workflow.
    """
    notes_dir = get_notes_dir()
    
    # Check if vault is initialized
    if not (notes_dir / "root.md").exists():
        if click.confirm("Vault not initialized. Initialize now?", default=True):
            ctx.invoke(init, yes=True)
            # Re-fetch notes_dir after init sets the vault path
            notes_dir = get_notes_dir()
        else:
            click.echo("Aborted.")
            return
    
    # Check if vault has content
    existing_files = list(notes_dir.glob("*.md"))
    if len(existing_files) > 2:  # More than root.md and backlog.md
        click.echo(f"Warning: Vault already contains {len(existing_files)} files.")
        if not click.confirm("Continue and add example content?", default=False):
            click.echo("Aborted.")
            return
    
    log_info("Creating example vault...")
    
    # Import subprocess to run cor commands
    def run_cor(*args):
        """Run a cor command."""
        result = subprocess.run(["cor", "-vv", *args], capture_output=True, text=True)
        if result.returncode != 0:
            click.echo(f"Error running: cor {' '.join(args)}", err=True)
            click.echo(result.stderr, err=True)
            return False
        return True
    
    ## ===== PROJECT 1: Foundation Model (active) =====
    run_cor("new", "project", "foundation_model", "--no_edit")
    # Create tasks in different statuses
    run_cor("new", "task", "foundation_model.dataset_curation", "-t", "Curate multi-domain corpus with strict filtering", "--no_edit")
    run_cor("new", "task", "foundation_model.training_pipeline", "-t", "Stand up distributed training stack", "--no_edit")
    run_cor("new", "task", "foundation_model.eval_harness", "-t", "Wire up eval harness for benchmarks", "--no_edit")
    run_cor("new", "task", "foundation_model.ablation_suite", "-t", "Design ablation study matrix", "--no_edit")
    
    # Mark tasks with different statuses
    run_cor("mark", "foundation_model.dataset_curation", "blocked")
    run_cor("mark", "foundation_model.training_pipeline", "active")
    run_cor("mark", "foundation_model.eval_harness", "waiting")
    run_cor("mark", "foundation_model.ablation_suite", "todo")
    
    # Create a task group for experiments
    run_cor("new", "task", "foundation_model.experiments.lr_sweep", "-t", "Run LR sweep across batch sizes", "--no_edit")
    run_cor("new", "task", "foundation_model.experiments.clip_tuning", "-t", "Tune gradient clipping thresholds", "--no_edit")
    run_cor("new", "task", "foundation_model.experiments.checkpoint_policy", "-t", "Test checkpoint cadence impact", "--no_edit")
    
    run_cor("mark", "foundation_model.experiments.lr_sweep", "done")
    run_cor("mark", "foundation_model.experiments.clip_tuning", "active")
    run_cor("mark", "foundation_model.experiments.checkpoint_policy", "todo")

    # Create another task group for data
    run_cor("new", "task", "foundation_model.data.tokenizer_refresh", "-t", "Re-train tokenizer with new domains", "--no_edit")
    run_cor("new", "task", "foundation_model.data.safety_filter", "-t", "Iterate on safety filtering rules", "--no_edit")
    
    run_cor("mark", "foundation_model.data.tokenizer_refresh", "active")
    run_cor("mark", "foundation_model.data.safety_filter", "todo")
    
    # Create notes under project
    run_cor("new", "note", "foundation_model.lab_notes", "-t", "Daily lab notebook entries", "--no_edit")
    run_cor("new", "note", "foundation_model.decisions", "-t", "Key modeling decisions and rationale", "--no_edit")
    
    # ===== PROJECT 2: Evaluation Suite (planning) =====
    run_cor("new", "project", "evaluation_suite", "--no_edit")
    
    run_cor("new", "task", "evaluation_suite.benchmark_catalog", "-t", "Select core academic and industry benchmarks", "--no_edit")
    run_cor("new", "task", "evaluation_suite.metric_defs", "-t", "Define metrics for safety and quality", "--no_edit")
    run_cor("new", "task", "evaluation_suite.reporting", "-t", "Automate eval report generation", "--no_edit")
    
    run_cor("mark", "evaluation_suite.benchmark_catalog", "todo")
    run_cor("mark", "evaluation_suite.metric_defs", "todo")
    run_cor("mark", "evaluation_suite.reporting", "todo")
    
    # ===== PROJECT 3: Paper Draft (paused) =====
    run_cor("new", "project", "paper", "--no_edit")
    
    run_cor("new", "task", "paper.related_work", "-t", "Summarize adjacent scaling papers", "--no_edit")
    run_cor("new", "task", "paper.method", "-t", "Write method section draft", "--no_edit")
    run_cor("new", "task", "paper.experiments", "-t", "Select figures for results", "--no_edit")
    
    run_cor("mark", "paper.related_work", "done")
    run_cor("mark", "paper.method", "active")
    run_cor("mark", "paper.experiments", "dropped")
    
    # ===== PROJECT 4: Baking (planning) =====
    run_cor("new", "project", "baking", "--no_edit")

    run_cor(
        "new",
        "task",
        "baking.test_new_flour",
        "-t",
        "Try high-protein flour against baseline",
        "--no_edit",
    )
    run_cor(
        "new",
        "task",
        "baking.new_recipe_from_link",
        "-t",
        "Review and plan bake from bookmarked recipe",
        "--no_edit",
    )
    run_cor(
        "new",
        "note",
        "baking.recipe_notebook",
        "-t",
        "Panettone formula notes from shared link",
        "--no_edit",
    )

    run_cor("mark", "baking.test_new_flour", "todo")
    run_cor("mark", "baking.new_recipe_from_link", "waiting")
    
    # ===== STANDALONE NOTES =====
    run_cor("new", "note", "random-ideas", "-t", "Brainstorm ideas for future projects", "--no_edit")
    run_cor("new", "note", "learning-log", "-t", "Track learning progress", "--no_edit")
    
    # ===== RENAME A PROJECT =====
    run_cor("rename", "evaluation_suite", "eval-suite", "--dry-run")
    run_cor("rename", "evaluation_suite", "eval-suite")
    
    click.echo("\n" + "="*60)
    click.echo("✓ Example vault created successfully!")
    click.echo("="*60)
    click.echo("\nTry these commands to explore:")
    click.echo("  cor daily           # See what needs attention")
    click.echo("  cor projects        # Overview of all projects")
    click.echo("  cor tree            # Hierarchical view")
    click.echo("  cor weekly          # Summarize recent work")
    click.echo("\nEdit files with:")
    click.echo("  cor edit foundation_model")
    click.echo("  cor edit foundation_model.training_pipeline")


@cli.command()
@click.argument("key", type=click.Choice(["verbosity", "vault"]), required=False)
@click.argument("value", required=False)
def config(key: str | None, value: str | None):
    """Manage CortexPKM configuration.

    View or modify global settings for verbosity and vault location.

    \b
    Configuration Keys:
      verbosity    Output detail level (0=silent, 1=normal, 2=verbose, 3=debug)
      vault        Path to your notes directory

    \b
    Examples:
      cor config                      Show all settings
      cor config verbosity 2          Set verbose output
      cor config vault ~/my-notes     Change vault location
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


@cli.command()
@click.argument("note_type", type=click.Choice(["project", "task", "note"]))
@click.argument("name", shell_complete=complete_name)
@click.option("--text", "-t", type=str, help="Brief description to add to the note/task")
@click.option("--no_edit", is_flag=True, help="Don't open in editor")
@require_init
def new(note_type: str, name: str, text: str | None, no_edit: bool):
    """Create a new project, task, or note.

    Use dot notation for hierarchy: project.task or project.group.task
    Task groups auto-create if they don't exist.

    \b
    Examples:
      cor new project my-project
      cor new task my-project.implement-feature
      cor new task my-project.bugs.fix-login    # Creates bugs group
      cor new note my-project.meeting-notes

    Note: Use hyphens in names, not dots (e.g., v0-1 not v0.1)
    """
    notes_dir = get_notes_dir()

    # Validate: dots are only for hierarchy, not within names
    parts = name.split(".")
    for part in parts:
        if not part:
            raise click.ClickException(
                "Invalid name: empty segment. Use 'project.task' format."
            )
    if note_type=="project" and "." in name:
        raise click.ClickException(
            f"Invalid project name '{name}': dots are reserved for hierarchy. "
            "Use hyphens instead (e.g., 'v0-1' not 'v0.1')."
        )

    # Parse dot notation for task/note: "project.taskname" or "project.group.taskname"
    task_name = name
    task_group, project = None, None
    if note_type in ("task", "note") and "." in name:
        # Reuse parts from validation above
        if len(parts) == 2:
            # project.task
            project = parts[0]
            task_name = parts[1]
        elif len(parts) == 3:
            # project.group.task
            project = parts[0]
            task_group = parts[1]
            task_name = parts[2]
        else:
            raise click.ClickException(
                "Invalid name: use 'project.task' or 'project.group.task' format."
            )

    # Build filename
    if note_type == "project":
        filename = f"{name}.md"
    else:
        if task_group:
            filename = f"{project}.{task_group}.{task_name}.md"
        elif project:
            filename = f"{project}.{task_name}.md"
        else:
            filename = f"{task_name}.md"

    filepath = notes_dir / filename
    filepath_archive = notes_dir / "archive" / filename

    if filepath.exists():
        raise click.ClickException(f"File already exists: {filepath}")
    if filepath_archive.exists():
        raise click.ClickException(f"File already exists in archive: {filepath_archive}")

    # Read and render template
    template = get_template(note_type)

    # Determine parent for task/note files
    parent = None
    parent_title = None
    if note_type in ("task", "note"):
        if task_group:
            # Task/note under a group: parent is the group
            parent = f"{project}.{task_group}"
            parent_title = format_title(task_group)
        elif project:
            # Task/note under project: parent is the project
            parent = project
            parent_title = format_title(project)

    content = render_template(template, task_name, parent, parent_title)

    filepath.write_text(content)
    log_info(f"Created {note_type} at {filepath}")

    # Handle task group hierarchy
    if note_type == "task" and task_group:
        group_filename = f"{project}.{task_group}"
        group_path = notes_dir / f"{group_filename}.md"
        archive_dir = notes_dir / "archive"

        # Check if group exists in archive (done/dropped) - unarchive it
        archived_group_path = archive_dir / f"{group_filename}.md"
        if archived_group_path.exists() and not group_path.exists():
            # Move from archive back to notes
            shutil.move(str(archived_group_path), group_path)

            # Update status to todo
            post = frontmatter.load(group_path)
            old_status = post.get('status', 'done')
            post['status'] = 'todo'
            with open(group_path, 'wb') as f:
                frontmatter.dump(post, f, sort_keys=False)

            click.echo(f"Unarchived {group_filename} ({old_status} → todo)")

            # Update link in parent project file
            project_path = notes_dir / f"{project}.md"
            if project_path.exists():
                content = project_path.read_text()
                # Update link from archive/ to direct
                pattern = rf'(\[[^\]]+\]\()archive/{re.escape(group_filename)}(\))'
                replacement = rf'\g<1>{group_filename}\g<2>'
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    project_path.write_text(new_content)

        # Create group file if it doesn't exist
        if not group_path.exists():
            group_template = get_template("task")
            # Group's parent is the project
            group_content = render_template(group_template, task_group, project, format_title(project))
            group_path.write_text(group_content)
            click.echo(f"Created {group_path}")

            # Add group to project's Tasks section
            project_path = notes_dir / f"{project}.md"
            add_task_to_project(project_path, task_group, group_filename)
            click.echo(f"Added to {project_path}")

        # Add task to group's Tasks section
        task_filename = filepath.stem
        add_task_to_project(group_path, task_name, task_filename)
        click.echo(f"Added to {group_path}")

    # Add task directly to project (no group)
    elif note_type == "task" and project:
        project_path = notes_dir / f"{project}.md"
        task_filename = filepath.stem
        add_task_to_project(project_path, task_name, task_filename)
        click.echo(f"Added to {project_path}")

    if text and note_type in ("task", "note"):
        click.echo("Added description text.")
        with filepath.open("r+") as f:
            content = f.read()
            content = content.replace("## Description\n", f"## Description\n\n{text}\n")
            f.seek(0)
            f.write(content)
            f.truncate()
    elif not no_edit:
       open_in_editor(filepath)


@cli.command()
@click.option("--archived", "-a", is_flag=True, is_eager=True, help="Include archived files in search")
@click.argument("name", shell_complete=complete_existing_name)
@require_init
def edit(archived: bool, name: str):
    """Open a file in your editor.

    Supports fuzzy matching - type partial names and select from matches.
    Use -a to include archived files in search.

    \b
    Examples:
      cor edit my-proj          # Fuzzy matches 'my-project'
      cor edit foundation       # Interactive picker if multiple matches
      cor edit -a old-project   # Include archived files
    """
    from .fuzzy import resolve_file_fuzzy, get_file_path

    # Handle "archive/" prefix if present (from tab completion)
    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    result = resolve_file_fuzzy(name, include_archived=archived)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    file_path = get_file_path(stem, is_archived)

    open_in_editor(file_path)


@cli.command(name="delete")
@click.option("--archived", "-a", is_flag=True, help="Include archived files in search")
@click.argument("name", shell_complete=complete_existing_name)
@require_init
def delete(archived: bool, name: str):
    """Delete a note quickly and update references.

    Supports fuzzy matching for file names.

    \b
    Examples:
        cor delete my-proj                  # Fuzzy matches 'my-project'
        cor delete -a old-project           # Include archived files
    """
    from .fuzzy import resolve_file_fuzzy, get_file_path

    notes_dir = get_notes_dir()

    # Handle "archive/" prefix if present (from tab completion)
    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    result = resolve_file_fuzzy(name, include_archived=archived)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    file_path = get_file_path(stem, is_archived)

    file_path.unlink()
    runner = MaintenanceRunner(notes_dir, dry_run=False)
    runner.sync([], deleted=[str(file_path)])
    click.echo(click.style(f"Deleted {stem}.md", fg="red"))


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

@cli.command()
@click.argument("name", shell_complete=complete_task_name)
@click.argument("status", shell_complete=complete_task_status)
@require_init
def mark(name: str, status: str):
    """Update task status.

    Supports fuzzy matching for task names.

    \b
    Status values:
      todo       Ready to start
      active     Currently working on
      done       Completed
      blocked    Waiting on external dependency
      waiting    Paused, waiting for information
      dropped    Abandoned/won't do

    \b
    Examples:
      cor mark impl active          # Fuzzy matches 'implement-api'
      cor mark my-project.research done
    """
    from .fuzzy import resolve_file_fuzzy, get_file_path

    notes_dir = get_notes_dir()

    # Use fuzzy matching (only active files, not archived)
    result = resolve_file_fuzzy(name, include_archived=False)

    if result is None:
        return  # User cancelled

    stem, _ = result
    file_path = notes_dir / f"{stem}.md"

    # Validate it's a task
    note = parse_note(file_path)

    if not note:
        raise click.ClickException(f"Could not parse file: {file_path}")

    if note.note_type != "task":
        raise click.ClickException(
            f"'{stem}' is a {note.note_type}, not a task. "
            "This command only works with tasks."
        )

    if status not in VALID_TASK_STATUS:
        raise click.ClickException(
            f"Invalid status '{status}'. "
            f"Valid: {', '.join(sorted(VALID_TASK_STATUS))}"
        )

    # Validate: task groups and projects cannot be marked done/dropped if children are incomplete
    if status in ("done", "dropped"):
        runner = MaintenanceRunner(notes_dir)
        task_name = note.path.stem
        incomplete = runner.get_incomplete_tasks(task_name)
        
        if incomplete:
            note_type = note.note_type
            if note_type == "task":
                raise click.ClickException(
                    f"Cannot mark task group as {status}. Incomplete tasks: {', '.join(incomplete)}"
                )

    # Load and update frontmatter
    post = frontmatter.load(file_path)

    if 'status' not in post.metadata:
        raise click.ClickException("Could not find status field in frontmatter")

    post['status'] = status

    # If status is waiting, add a due date of 1 day
    if status == "waiting":
        due_date = (datetime.now() + timedelta(days=1)).strftime(DATE_TIME)
        post['due'] = due_date

    with open(file_path, 'wb') as f:
        frontmatter.dump(post, f, sort_keys=False)

    # Run sync for immediate feedback
    runner = MaintenanceRunner(notes_dir)
    runner.sync([str(file_path)])

    # Status display
    old_status = note.status or "none"
    symbol = STATUS_SYMBOLS.get(status, "")
    location = ""

    click.echo(f"{symbol} {note.title}: {old_status} → {click.style(status, bold=True)}{location}")


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
    # Find git directory
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

    # Copy pre-commit hook
    source = HOOKS_DIR / "pre-commit"
    target = hooks_target / "pre-commit"

    if not source.exists():
        raise click.ClickException(f"Hook source not found: {source}")

    if target.exists():
        click.echo(f"Overwriting existing {target}")

    shutil.copy(source, target)

    # Make executable
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    click.echo(f"Installed pre-commit hook to {target}")

    # Install conda activate hook for shell completion
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        activate_dir = Path(conda_prefix) / "etc" / "conda" / "activate.d"
        activate_dir.mkdir(parents=True, exist_ok=True)

        completion_script = activate_dir / "cor-completion.sh"
        # Cortex shell completion for zsh and bash
        completion_script.write_text('''\
# Cortex shell completion (zsh and bash)
if [ -n "$ZSH_VERSION" ]; then
    _cor_completion() {
        local -a completions completions_partial
        local -a response
        (( ! $+commands[cor] )) && return 1

        response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT-1)) _COR_COMPLETE=zsh_complete cor)}")

        # click zsh completion returns triples: type, value, help per item
        local i=1
        local rlen=${#response}
        while (( i <= rlen )); do
            local type=${response[i]}
            local key=${response[i+1]:-}
            local descr=${response[i+2]:-}
            (( i += 3 ))
            if [[ "$type" == "plain" && -n "$key" ]]; then
                if [[ "$key" == *. ]]; then
                    # Partial completion (ends with .) - no trailing space
                    completions_partial+=("$key")
                else
                    completions+=("$key")
                fi
            fi
        done

        # If nothing to add, decline completion so zsh doesn't clobber input
        if [[ ${#completions_partial} -eq 0 && ${#completions} -eq 0 ]]; then
            return 1
        fi

        if [[ ${#completions_partial} -gt 0 ]]; then
            # -Q to quote special chars; provide list explicitly to avoid odd edge cases
            compadd -Q -U -S '' -V partial -- ${completions_partial[@]}
        fi
        if [[ ${#completions} -gt 0 ]]; then
            compadd -Q -U -V unsorted -- ${completions[@]}
        fi
    }
    compdef _cor_completion cor
elif [ -n "$BASH_VERSION" ]; then
    eval "$(_COR_COMPLETE=bash_source cor)"
fi
''')
        click.echo(f"Installed shell completion to {completion_script}")
        click.echo("Reactivate conda environment")
    else:
        click.echo("No conda environment detected. For shell completion, add to ~/.zshrc:")
        click.echo('  eval "$(_COR_COMPLETE=zsh_source cor)"')


@hooks.command("uninstall")
def hooks_uninstall():
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


@cli.group()
def maintenance():
    """Maintenance operations for the vault.

    Run maintenance tasks like syncing archive/unarchive,
    updating checkboxes, and sorting tasks.
    """
    pass


@maintenance.command("sync")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@click.option("--all", "-a", "sync_all", is_flag=True, help="Sync all files, not just modified")
@require_init
def maintenance_sync(dry_run: bool, sync_all: bool):
    """Synchronize vault state: archive, status, checkboxes, sorting.

    By default, syncs files that have been modified according to git.
    Use --all to sync the entire vault.

    Examples:
        cor maintenance sync              # Sync git-modified files
        cor maintenance sync --dry-run    # Preview changes
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

    runner = MaintenanceRunner(notes_dir, dry_run=dry_run)
    result = runner.sync(files)

    if dry_run:
        click.echo(click.style("=== Dry Run ===\n", bold=True, fg="yellow"))

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
    elif dry_run:
        click.echo(click.style("\nNo changes made (dry run).", fg="yellow"))
    else:
        click.echo(click.style("\nDone!", fg="green"))

# Register commands from modules
cli.add_command(daily)
cli.add_command(projects)
cli.add_command(weekly)
cli.add_command(tree)
cli.add_command(review)
cli.add_command(rename)
cli.add_command(rename, name="move")  # Alias for rename
cli.add_command(group)
cli.add_command(process)
cli.add_command(delete, name="del")  # Alias for delete


if __name__ == "__main__":
    cli()
