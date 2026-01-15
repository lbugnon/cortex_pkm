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
from .commands import daily, projects, weekly, tree, review, rename, group, process, log
from .commands.dependencies import depend
from .commands.refs import ref
from .completions import complete_name, complete_task_name, complete_task_status, complete_existing_name
from .config import set_vault_path, load_config, config_file, set_verbosity, get_verbosity
from .sync import MaintenanceRunner
from .core.notes import parse_metadata
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
    parse_natural_language_text,
)

HOOKS_DIR = Path(__file__).parent / "hooks"


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
    
    Creates the vault structure (notes/, templates/, root.md, backlog.md).
    Initializes git repository if not already present.
    Installs git hooks and configures shell completion automatically.
    Sets this directory as your vault path in the global config.
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

    # Check if git repository exists, create if it doesn't
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        cwd=vault_path,
    )
    if result.returncode != 0:
        # Initialize git repository
        log_verbose("Initializing git repository...")
        subprocess.run(["git", "init"], cwd=vault_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "CortexPKM"], cwd=vault_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "cortex@local"], cwd=vault_path, capture_output=True)
        log_info("Git repository initialized.")
    
    # Install git hooks
    ctx.invoke(hooks_install)


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
    - Academic references (papers from CrossRef)
    
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
    run_cor("new", "project", "foundation_model", "--no-edit")
    # Create tasks in different statuses
    run_cor("new", "task", "foundation_model.dataset_curation", "-t", "Curate multi-domain corpus with strict filtering", "--no-edit")
    run_cor("new", "task", "foundation_model.training_pipeline", "-t", "Stand up distributed training stack", "--no-edit")
    run_cor("new", "task", "foundation_model.eval_harness", "-t", "Wire up eval harness for benchmarks", "--no-edit")
    run_cor("new", "task", "foundation_model.ablation_suite", "-t", "Design ablation study matrix", "--no-edit")
    
    # Mark tasks with different statuses
    run_cor("mark", "foundation_model.dataset_curation", "blocked")
    run_cor("mark", "foundation_model.training_pipeline", "active")
    run_cor("mark", "foundation_model.eval_harness", "waiting")
    run_cor("mark", "foundation_model.ablation_suite", "todo")
    
    # Create a task group for experiments
    run_cor("new", "task", "foundation_model.experiments.lr_sweep", "-t", "Run LR sweep across batch sizes", "--no-edit")
    run_cor("new", "task", "foundation_model.experiments.clip_tuning", "-t", "Tune gradient clipping thresholds", "--no-edit")
    run_cor("new", "task", "foundation_model.experiments.checkpoint_policy", "-t", "Test checkpoint cadence impact", "--no-edit")
    
    run_cor("mark", "foundation_model.experiments.lr_sweep", "done")
    run_cor("mark", "foundation_model.experiments.clip_tuning", "active")
    run_cor("mark", "foundation_model.experiments.checkpoint_policy", "todo")

    # Create another task group for data
    run_cor("new", "task", "foundation_model.data.tokenizer_refresh", "-t", "Re-train tokenizer with new domains", "--no-edit")
    run_cor("new", "task", "foundation_model.data.safety_filter", "-t", "Iterate on safety filtering rules", "--no-edit")
    
    run_cor("mark", "foundation_model.data.tokenizer_refresh", "active")
    run_cor("mark", "foundation_model.data.safety_filter", "todo")
    
    # Create notes under project
    run_cor("new", "note", "foundation_model.lab_notes", "-t", "Daily lab notebook entries", "--no-edit")
    run_cor("new", "note", "foundation_model.decisions", "-t", "Key modeling decisions and rationale", "--no-edit")
    
    # ===== PROJECT 2: Evaluation Suite (planning) =====
    run_cor("new", "project", "evaluation_suite", "--no-edit")
    
    run_cor("new", "task", "evaluation_suite.benchmark_catalog", "-t", "Select core academic and industry benchmarks", "--no-edit")
    run_cor("new", "task", "evaluation_suite.metric_defs", "-t", "Define metrics for safety and quality", "--no-edit")
    run_cor("new", "task", "evaluation_suite.reporting", "-t", "Automate eval report generation", "--no-edit")
    
    run_cor("mark", "evaluation_suite.benchmark_catalog", "todo")
    run_cor("mark", "evaluation_suite.metric_defs", "todo")
    run_cor("mark", "evaluation_suite.reporting", "todo")
    
    # ===== PROJECT 3: Paper Draft (paused) =====
    run_cor("new", "project", "paper", "--no-edit")
    
    run_cor("new", "task", "paper.related_work", "-t", "Summarize adjacent scaling papers", "--no-edit")
    run_cor("new", "task", "paper.method", "-t", "Write method section draft", "--no-edit")
    run_cor("new", "task", "paper.experiments", "-t", "Select figures for results", "--no-edit")
    
    run_cor("mark", "paper.related_work", "done")
    run_cor("mark", "paper.method", "active")
    run_cor("mark", "paper.experiments", "dropped")
    
    # ===== PROJECT 4: Baking (planning) =====
    run_cor("new", "project", "baking", "--no-edit")

    run_cor(
        "new",
        "task",
        "baking.test_new_flour",
        "-t",
        "Try high-protein flour against baseline",
        "--no-edit",
    )
    run_cor(
        "new",
        "task",
        "baking.new_recipe_from_link",
        "-t",
        "Review and plan bake from bookmarked recipe",
        "--no-edit",
    )
    run_cor(
        "new",
        "note",
        "baking.recipe_notebook",
        "-t",
        "Panettone formula notes from shared link",
        "--no-edit",
    )

    run_cor("mark", "baking.test_new_flour", "todo")
    run_cor("mark", "baking.new_recipe_from_link", "waiting")
    
    # ===== STANDALONE NOTES =====
    run_cor("new", "note", "random-ideas", "-t", "Brainstorm ideas for future projects", "--no-edit")
    run_cor("new", "note", "learning-log", "-t", "Track learning progress", "--no-edit")
    
    # ===== REFERENCES =====
    log_info("Adding reference examples...")
    # Add influential papers related to the foundation model project
    run_cor("ref", "add", "10.48550/arXiv.1706.03762", "--key", "vaswani2017attention", "--no-edit")  # Attention Is All You Need
    run_cor("ref", "add", "10.48550/arXiv.1810.04805", "--key", "devlin2018bert", "--no-edit")  # BERT
    run_cor("ref", "add", "10.48550/arXiv.2005.14165", "--key", "brown2020gpt3", "--no-edit")  # GPT-3
    run_cor("ref", "add", "10.48550/arXiv.2203.02155", "--no-edit")  # InstructGPT, key is optional
    
    # ===== RENAME A PROJECT =====
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
    click.echo("\nExplore references:")
    click.echo("  cor ref list        # View all references")
    click.echo("  cor ref show vaswani2017attention")
    click.echo("  [to be implemented] cor ref search transformer")


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
@click.argument("text", nargs=-1)
@click.option("--no-edit", is_flag=True, help="Do not open the new file in editor")
@require_init
def new(note_type: str, name: str, text: tuple[str, ...], no_edit: bool):
    """Create a new project, task, or note.

    Use dot notation for hierarchy: project.task, project.group.task, or deeper
    Task groups auto-create if they don't exist.

    \b
    Examples:
      cor new project my-project
      cor new task my-project.implement-feature
      cor new task my-project.bugs.fix-login              # Creates bugs group
      cor new task my-project.experiments.lr.sweep        # Creates nested groups
      cor new note my-project.meeting-notes
      
    \b
    Natural language dates and tags (for tasks/notes):
      cor new task proj.task finish pipeline due tomorrow
      cor new task proj.task fix bug tag urgent ml
      cor new task proj.task code review due next friday tag review

    Note: Use hyphens in names, not dots (e.g., v0-1 not v0.1)
    """
    notes_dir = get_notes_dir()

    # Join text tuple into a single string early for easier processing
    text = " ".join(text) if text else None

    # Validate: dots are only for hierarchy, not within names
    parts = name.split(".")
    for part in parts:
        if not part:
            raise click.ClickException(
                "Invalid name: empty segment. Use 'project.task' format."
            )
        if "&" in part:
            raise click.ClickException(
                "Invalid name: '&' is not allowed in note names."
            )
    if note_type=="project" and "." in name:
        raise click.ClickException(
            f"Invalid project name '{name}': dots are reserved for hierarchy. "
            "Use hyphens instead (e.g., 'v0-1' not 'v0.1')."
        )

    # Parse dot notation for task/note: "project.taskname" or "project.group.taskname" or "project.group.smaller_group.task"
    task_name = name
    parent_hierarchy, project = None, None
    if note_type in ("task", "note") and "." in name:
        # Reuse parts from validation above
        if len(parts) == 2:
            # project.task
            project = parts[0]
            task_name = parts[1]
        elif len(parts) >= 3:
            # project.group.task or project.group.smaller_group.task (or deeper)
            project = parts[0]
            parent_hierarchy = ".".join(parts[:-1])  # Everything except the last part
            task_name = parts[-1]
        else:
            raise click.ClickException(
                "Invalid name: use 'project.task', 'project.group.task', or deeper hierarchy format."
            )

    # Build filename
    if note_type == "project":
        filename = f"{name}.md"
    else:
        if parent_hierarchy:
            # Use full parent hierarchy: project.group.smaller_group.task
            filename = f"{parent_hierarchy}.{task_name}.md"
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
        if parent_hierarchy:
            # Task/note under a parent hierarchy (group or deeper)
            parent = parent_hierarchy
            # Extract the last component for the title (immediate parent)
            parent_title = format_title(parent_hierarchy.split(".")[-1])
        elif project:
            # Task/note under project: parent is the project
            parent = project
            parent_title = format_title(project)

    content = render_template(template, task_name, parent, parent_title)

    filepath.write_text(content)
    log_info(f"Created {note_type} at {filepath}")

    # Handle task group hierarchy - auto-create missing parent groups
    if note_type == "task" and parent_hierarchy:
        # For hierarchy like project.group.smaller_group.task, we need to ensure:
        # 1. project.group exists
        # 2. project.group.smaller_group exists
        # 3. Add task to the immediate parent
        
        # Split parent hierarchy into parts
        parent_parts = parent_hierarchy.split(".")
        
        # Create all missing parent groups in the hierarchy
        for i in range(1, len(parent_parts)):
            # Build the group name at this level
            group_stem = ".".join(parent_parts[:i+1])
            group_path = notes_dir / f"{group_stem}.md"
            archive_dir = notes_dir / "archive"
            
            # Check if group exists in archive (done/dropped) - unarchive it
            archived_group_path = archive_dir / f"{group_stem}.md"
            if archived_group_path.exists() and not group_path.exists():
                # Move from archive back to notes
                shutil.move(str(archived_group_path), group_path)
                
                # Update status to todo
                post = frontmatter.load(group_path)
                old_status = post.get('status', 'done')
                post['status'] = 'todo'
                with open(group_path, 'wb') as f:
                    frontmatter.dump(post, f, sort_keys=False)
                
                click.echo(f"Unarchived {group_stem} ({old_status} → todo)")
                
                # Update link in parent file
                parent_stem = ".".join(parent_parts[:i]) if i > 1 else parent_parts[0]
                parent_path = notes_dir / f"{parent_stem}.md"
                if parent_path.exists():
                    content = parent_path.read_text()
                    # Update link from archive/ to direct
                    pattern = rf'(\[[^\]]+\]\()archive/{re.escape(group_stem)}(\))'
                    replacement = rf'\g<1>{group_stem}\g<2>'
                    new_content = re.sub(pattern, replacement, content)
                    if new_content != content:
                        parent_path.write_text(new_content)
            
            # Create group file if it doesn't exist
            if not group_path.exists():
                group_template = get_template("task")
                # Group's parent is the previous level in hierarchy
                group_parent = ".".join(parent_parts[:i]) if i > 1 else parent_parts[0]
                group_name = parent_parts[i]
                group_content = render_template(group_template, group_name, group_parent, format_title(group_parent.split(".")[-1]))
                group_path.write_text(group_content)
                click.echo(f"Created {group_path}")
                
                # Add group to its parent's Tasks section
                parent_path = notes_dir / f"{group_parent}.md"
                add_task_to_project(parent_path, group_name, group_stem)
                click.echo(f"Added to {parent_path}")
        
        # Add task to the immediate parent's Tasks section
        immediate_parent_path = notes_dir / f"{parent_hierarchy}.md"
        task_filename = filepath.stem
        add_task_to_project(immediate_parent_path, task_name, task_filename)
        click.echo(f"Added to {immediate_parent_path}")

    # Add task directly to project (no group)
    elif note_type == "task" and project:
        project_path = notes_dir / f"{project}.md"
        task_filename = filepath.stem
        add_task_to_project(project_path, task_name, task_filename)
        click.echo(f"Added to {project_path}")
    
    if text:
        text = " ".join(text)
    
    if text and note_type in ("task", "note"):
        # Parse natural language dates and tags
        cleaned_text, due_date, parsed_tags = parse_natural_language_text(text)
        
        # Update the description with cleaned text
        if cleaned_text:
            click.echo("Added description text.")
            with filepath.open("r+") as f:
                content = f.read()
                content = content.replace("## Description\n", f"## Description\n\n{cleaned_text}\n")
                f.seek(0)
                f.write(content)
                f.truncate()
        
        # Add due date if parsed
        if due_date:
            post = frontmatter.load(filepath)
            post['due'] = due_date.strftime(DATE_TIME)
            with open(filepath, 'wb') as f:
                frontmatter.dump(post, f, sort_keys=False)
            click.echo(f"Set due date: {due_date.strftime(DATE_TIME)}")
        
        # Add tags if parsed
        if parsed_tags:
            post = frontmatter.load(filepath)
            existing_tags = post.get("tags", [])
            new_tags = existing_tags + [t for t in parsed_tags if t not in existing_tags]
            post["tags"] = new_tags
            with open(filepath, 'wb') as f:
                frontmatter.dump(post, f, sort_keys=False)
            click.echo(f"Added tags: {', '.join(parsed_tags)}")
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
    from .search import resolve_file_fuzzy, get_file_path

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


@cli.command()
@click.option("--archived", "-a", is_flag=True, help="Include archived files in search")
@click.option("--delete", "-d", "delete_tags", is_flag=True, help="Remove provided tags instead of adding")
@click.argument("name", shell_complete=complete_existing_name)
@click.argument("tags", nargs=-1)
@require_init
def tag(archived: bool, delete_tags: bool, name: str, tags: tuple[str, ...]):
    """Add or remove tags on a note.

    Uses the same fuzzy search as `cor edit`.

    Examples:
      cor tag foundation_model ml research
      cor tag -d foundation_model ml
    """
    from .search import resolve_file_fuzzy, get_file_path

    if not tags:
        raise click.ClickException("Provide at least one tag to add or remove.")

    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    result = resolve_file_fuzzy(name, include_archived=archived)
    if result is None:
        return

    stem, is_archived = result
    file_path = get_file_path(stem, is_archived)

    post = frontmatter.load(file_path)

    existing = post.get("tags", [])
    
    if delete_tags:
        new_tags = [t for t in existing if t not in tags]
        if len(new_tags) == len(existing):
            log_info("No matching tags to remove.")
            return
        summary = f"Removed tags from {stem}: {', '.join(sorted(set(existing) - set(new_tags)))}"
    else:
        to_add = [t for t in tags if t not in existing]
        if not to_add:
            log_info("Tags already up to date.")
            return
        new_tags = existing + to_add
        summary = f"Added tags to {stem}: {', '.join(to_add)}"

    post["tags"] = new_tags
    post["modified"] = datetime.now().strftime(DATE_TIME)
    with open(file_path, "wb") as f:
        frontmatter.dump(post, f, sort_keys=False)

    # Rewrite tag list in flow style: tags: [a, b]
    # Avoid matching YAML frontmatter delimiters (---) by requiring a space after '-'
    text = Path(file_path).read_text()
    pattern = re.compile(r"(^tags:\s*\n(?:\s+-\s*[^\n]+\n)+)", re.MULTILINE)

    def _inline_tags(match):
        lines = match.group(0).splitlines()
        values = [re.sub(r"^\s*-\s*", "", ln).strip() for ln in lines[1:]]
        return f"tags: [{', '.join(values)}]\n"

    new_text = pattern.sub(_inline_tags, text)
    if new_text != text:
        Path(file_path).write_text(new_text)

    log_info(summary)


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
    from .search import resolve_file_fuzzy, get_file_path

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
    runner = MaintenanceRunner(notes_dir)
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
@click.argument("text", nargs=-1, type=str)
@require_init
def mark(name: str, status: str, text: str | None):
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
      cor mark task-name done -t "Completed the implementation"
    """
    from .search import resolve_file_fuzzy, get_file_path

    notes_dir = get_notes_dir()

    # Use fuzzy matching (only active files, not archived)
    result = resolve_file_fuzzy(name, include_archived=False)

    if result is None:
        return  # User cancelled

    stem, _ = result
    file_path = notes_dir / f"{stem}.md"

    # Validate it's a task (metadata only - faster)
    note = parse_metadata(file_path)

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

    # Append text if provided
    if text:
        text = " ".join(text)
        # Add text to the content
        post.content = post.content.rstrip() + f"\n{text}"

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
    
    if text:
        click.echo(f"  Added note: {text}")


@cli.command()
@click.argument("name", shell_complete=complete_existing_name)
@require_init
def expand(name: str):
    """Expand task checklist into individual subtasks.

    Parses checklist items from a task's description and creates individual
    subtask files. The original task becomes a task group with proper links.

    \b
    Examples:
      cor expand myproject.feature
      cor expand paper.experiments.md
      cor expand -a archived-task           # Include archived files

    \b
    Before (task with checklist):
      ## Description
      - [ ] design-api
      - [ ] implement-backend
      - [ ] write-tests

    \b
    After:
      Creates: myproject.feature.design-api.md
               myproject.feature.implement-backend.md
               myproject.feature.write-tests.md
      Updates: myproject.feature.md with task links
    """
    from .search import resolve_file_fuzzy, get_file_path
    from .utils import parse_checklist_items, remove_checklist_items

    notes_dir = get_notes_dir()

    # Remove .md extension if present
    if name.endswith('.md'):
        name = name[:-3]

    # Use fuzzy matching to resolve task name
    result = resolve_file_fuzzy(name, include_archived=False)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    task_file = get_file_path(stem, is_archived)

    # Parse the task file
    post = frontmatter.load(task_file)

    # Verify it's a task
    if post.get('type') != 'task':
        raise click.ClickException(f"File is not a task: {task_file}")

    # Extract checklist items from content
    checklist_items = parse_checklist_items(post.content)

    if not checklist_items:
        raise click.ClickException(
            f"No checklist items found in {task_file.name}. "
            "Add unchecked items like '- [ ] subtask-name' to the Description section."
        )

    # Get the task stem (filename without .md)
    task_stem = task_file.stem

    # Determine parent info
    parent = post.get('parent')
    if not parent:
        raise click.ClickException(f"Task has no parent field: {task_file}")

    log_info(click.style(f"Expanding {task_stem} into {len(checklist_items)} subtasks...", fg="cyan"))

    # Create subtask files
    template = get_template("task")
    created_files = []

    for task_name, task_status, task_text in checklist_items:
        subtask_filename = f"{task_stem}.{task_name}.md"
        subtask_path = notes_dir / subtask_filename

        if subtask_path.exists():
            click.echo(f"Warning: {subtask_filename} already exists, skipping")
            continue

        # Render subtask content with task as parent, using original task text as title
        subtask_content = render_template(
            template, 
            task_name, 
            parent=task_stem,
            parent_title=format_title(task_stem.split('.')[-1]),
            title=task_text
        )

        # Parse the rendered content and set the status from checklist
        subtask_post = frontmatter.loads(subtask_content)
        subtask_post['status'] = task_status
        subtask_post['title'] = task_text
        
        # Write subtask with correct status
        with open(subtask_path, 'wb') as f:
            frontmatter.dump(subtask_post, f, sort_keys=False)
        
        created_files.append((task_name, subtask_filename, task_status))
        log_verbose(f"  Created {subtask_filename} (status: {task_status})")

    # Remove checklist items from original task content
    new_content = remove_checklist_items(post.content)
    post.content = new_content

    # Write updated task file
    with open(task_file, 'wb') as f:
        frontmatter.dump(post, f, sort_keys=False)

    # Add subtask links to the task file (now acting as group)
    for task_name, subtask_filename, _ in created_files:
        add_task_to_project(task_file, task_name, subtask_filename.replace('.md', ''))

    log_info(click.style(f"\nSuccess! Created {len(created_files)} subtasks under {task_stem}", fg="green"))
    for task_name, filename, status in created_files:
        log_info(f"  - {filename} (status: {status})")


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

    # Detect shell and install completion
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
    
    # Check if completion is already installed
    if zshrc.exists():
        content = zshrc.read_text()
        if "# Cortex shell completion" in content or "_cor_completion" in content:
            click.echo("Shell completion already configured in ~/.zshrc")
            return
    
    # Append completion block
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
    
    # Check if completion is already installed
    if bashrc.exists():
        content = bashrc.read_text()
        if "# Cortex shell completion" in content or "_COR_COMPLETE=bash_source" in content:
            click.echo("Shell completion already configured in ~/.bashrc")
            return
    
    # Append completion block
    with bashrc.open("a") as f:
        f.write(completion_block)
    
    click.echo("Added shell completion to ~/.bashrc")
    click.echo("Run 'source ~/.bashrc' or restart your shell to enable")


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
cli.add_command(log)
cli.add_command(delete, name="del")  # Alias for delete
cli.add_command(depend)
cli.add_command(ref)


if __name__ == "__main__":
    cli()
