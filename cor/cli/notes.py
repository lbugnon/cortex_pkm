"""Note and task management commands for Cortex CLI."""

import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
import frontmatter

from . import cli
from ..exceptions import ValidationError, NotFoundError, AlreadyExistsError
from ..schema import VALID_TASK_STATUS, STATUS_SYMBOLS, DATE_TIME
from ..config import get_focused_project
from ..core.notes import parse_metadata
from ..sync import MaintenanceRunner
from ..utils import (
    get_notes_dir,
    get_template,
    format_title,
    render_template,
    open_in_editor,
    add_task_to_project,
    require_init,
    log_info,
    log_verbose,
    parse_natural_language_text,
    read_h1,
    title_to_stem,
)
from ..completions import complete_name, complete_task_name, complete_task_status, complete_existing_name
from ..search import resolve_file_fuzzy, get_file_path, resolve_task_fuzzy


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

    # Validate: dots are only for hierarchy, not within names
    parts = name.split(".")
    for part in parts:
        if not part:
            raise ValidationError(
                "Invalid name: empty segment. Use 'project.task' format."
            )
        if "&" in part:
            raise ValidationError(
                "Invalid name: '&' is not allowed in note names."
            )
    if note_type=="project" and "." in name:
        raise ValidationError(
            f"Invalid project name '{name}': dots are reserved for hierarchy. "
            "Use hyphens instead (e.g., 'v0-1' not 'v0.1')."
        )

    # Parse dot notation for task/note: "project.taskname" or "project.group.taskname" or "project.group.smaller_group.task"
    task_name = name
    parent_hierarchy, project = None, None
    
    # Apply focus if set and no project specified
    if note_type in ("task", "note") and "." not in name:
        focused = get_focused_project()
        if focused:
            # Prepend focused project to the name
            name = f"{focused}.{name}"
            parts = name.split(".")
    
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
            raise ValidationError(
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

    if filepath.exists():
        raise AlreadyExistsError(f"File already exists: {filepath}")
    # Note: We don't check archive by default (consistent with edit/mark/move)
    # Archived files don't block creating new files with the same name

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
                    pattern = rf'(\[[^\]]+\]\()archive/{re.escape(group_stem)}\.md(\))'
                    replacement = rf'\g<1>{group_stem}.md\g<2>'
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
    
    text_was_provided = False
    if text and note_type in ("task", "note"):
        text_was_provided = True
        # Parse natural language dates, tags, and status
        cleaned_text, due_date, parsed_tags, parsed_status = parse_natural_language_text(text)
        
        # Update the description with cleaned text (only if there's actual text left)
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
        
        # Set status if parsed (only for tasks)
        if parsed_status and note_type == "task":
            post = frontmatter.load(filepath)
            post['status'] = parsed_status
            with open(filepath, 'wb') as f:
                frontmatter.dump(post, f, sort_keys=False)
            click.echo(f"Set status: {parsed_status}")
    
    # Open editor only if no text was provided (and --no-edit not set)
    if not text_was_provided and not no_edit:
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
    notes_dir = get_notes_dir()

    # Handle "archive/" prefix if present (from tab completion)
    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    # Get focused project for prioritization
    focused = get_focused_project()
    result = resolve_file_fuzzy(name, include_archived=archived, focused_project=focused)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    file_path = get_file_path(stem, is_archived)

    h1_before = read_h1(file_path)
    open_in_editor(file_path)
    h1_after = read_h1(file_path)

    if h1_after and h1_after != h1_before:
        old_leaf = stem.split(".")[-1]
        new_leaf = title_to_stem(h1_after)
        if new_leaf and new_leaf != old_leaf and h1_after.lower() != format_title(old_leaf).lower():
            new_stem = ".".join(stem.split(".")[:-1] + [new_leaf]) if "." in stem else new_leaf
            from ..commands.refactor import rename as rename_cmd
            ctx = click.get_current_context()
            ctx.invoke(rename_cmd, old_name=stem, new_name=new_stem, archived=is_archived, dry_run=False)
            click.echo(click.style(f"Renamed \u2192 {new_stem}", fg="cyan"))


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
    if not tags:
        raise ValidationError("Provide at least one tag to add or remove.")

    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    # Get focused project for prioritization
    focused = get_focused_project()
    result = resolve_file_fuzzy(name, include_archived=archived, focused_project=focused)
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
    notes_dir = get_notes_dir()

    # Handle "archive/" prefix if present (from tab completion)
    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    # Get focused project for prioritization
    focused = get_focused_project()
    result = resolve_file_fuzzy(name, include_archived=archived, focused_project=focused)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    file_path = get_file_path(stem, is_archived)

    file_path.unlink()
    runner = MaintenanceRunner(notes_dir)
    runner.sync([], deleted=[str(file_path)])
    click.echo(click.style(f"Deleted {stem}.md", fg="red"))


@cli.command()
@click.option("--archived", "-a", is_flag=True, is_eager=True, help="Include archived files in search")
@click.option("--status", "-s", "status_option", type=str, help="New status value (alternative positional arg)")
@click.argument("name", shell_complete=complete_task_name)
@click.argument("status", shell_complete=complete_task_status, required=False)
@click.argument("text", nargs=-1, type=str)
@require_init
def mark(archived: bool, status_option: str | None, name: str, status: str | None, text: tuple[str, ...]):
    """Update task status.

    Supports fuzzy matching for task names and glob patterns for bulk updates.

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
      cor mark impl active                    # Fuzzy matches 'implement-api'
      cor mark my-project.research done       # Specific task
      cor mark -a old-task todo               # Search archived tasks too
      cor mark "project.*" done               # Bulk: mark all project tasks done
      cor mark -s done "project.*"            # Alternative: --status before pattern
      cor mark project.group.* active         # Bulk: mark group tasks active
    """
    from fnmatch import fnmatch
    from ..utils import is_glob_pattern, expand_glob_to_stems

    notes_dir = get_notes_dir()

    # Determine the actual status value (from --status option or positional arg)
    actual_status = status_option or status
    
    # Handle case where name might be the pattern and status is in the option
    if actual_status is None:
        raise ValidationError(
            "Status is required. Usage: cor mark <task> <status> or cor mark -s <status> <task>"
        )
    
    # Validate status
    if actual_status not in VALID_TASK_STATUS:
        raise ValidationError(
            f"Invalid status '{actual_status}'. "
            f"Valid: {', '.join(sorted(VALID_TASK_STATUS))}"
        )

    # Handle archive/ prefix from tab completion
    if name.startswith("archive/"):
        name = name[8:]
        archived = True

    # Check if name is a glob pattern
    if is_glob_pattern(name):
        # Bulk operation using glob pattern
        _mark_bulk(name, actual_status, text, notes_dir, archived)
        return

    # Single file operation with fuzzy matching
    focused = get_focused_project()
    result = resolve_task_fuzzy(name, include_archived=archived, focused_project=focused)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    file_path = get_file_path(stem, is_archived)

    # Validate it's a task (metadata only - faster)
    note = parse_metadata(file_path)

    if not note:
        raise NotFoundError(f"Could not parse file: {file_path}")

    if note.note_type != "task":
        raise ValidationError(
            f"'{stem}' is a {note.note_type}, not a task. "
            "This command only works with tasks."
        )

    _update_task_status(file_path, note, actual_status, text, notes_dir)


def _mark_bulk(pattern: str, status: str, text: tuple[str, ...], notes_dir: Path, include_archive: bool):
    """Mark multiple tasks matching a glob pattern.
    
    Args:
        pattern: Glob pattern to match tasks
        status: New status value
        text: Optional text to append
        notes_dir: Path to notes directory
        include_archive: Whether to include archived files
    """
    from ..utils import expand_glob_pattern
    
    # Find all matching task files
    matching_files = expand_glob_pattern(pattern, notes_dir, include_archive)
    
    # Filter to only tasks (not projects or notes)
    task_files = []
    for file_path in matching_files:
        note = parse_metadata(file_path)
        if note and note.note_type == "task":
            task_files.append((file_path, note))
    
    if not task_files:
        raise NotFoundError(f"No tasks match pattern: {pattern}")
    
    # Confirm bulk operation if more than 3 files
    if len(task_files) > 3:
        click.echo(f"Will update {len(task_files)} tasks to '{status}':")
        for file_path, note in task_files[:5]:
            click.echo(f"  - {file_path.stem} ({note.status or 'none'} → {status})")
        if len(task_files) > 5:
            click.echo(f"  ... and {len(task_files) - 5} more")
        
        # In non-interactive mode, auto-continue; otherwise prompt
        if sys.stdin.isatty():
            if not click.confirm("Continue?"):
                click.echo("Cancelled.")
                return
        else:
            click.echo("Non-interactive mode: proceeding with update.")
    
    # Update each task
    updated_count = 0
    error_count = 0
    files_to_sync = []
    
    for file_path, note in task_files:
        try:
            _update_task_status(file_path, note, status, text, notes_dir, display=False)
            files_to_sync.append(str(file_path))
            updated_count += 1
        except ValidationError as e:
            click.secho(f"  Skipped {file_path.stem}: {e}", fg="yellow")
            error_count += 1
        except Exception as e:
            click.secho(f"  Error {file_path.stem}: {e}", fg="red")
            error_count += 1
    
    # Run sync for all updated files
    if files_to_sync:
        runner = MaintenanceRunner(notes_dir)
        runner.sync(files_to_sync)
    
    # Summary
    symbol = STATUS_SYMBOLS.get(status, "")
    click.echo(f"\n{symbol} Updated {updated_count} task(s) to {click.style(status, bold=True)}")
    if error_count:
        click.echo(f"  ({error_count} skipped due to errors)")


def _update_task_status(
    file_path: Path, 
    note, 
    status: str, 
    text: tuple[str, ...], 
    notes_dir: Path,
    display: bool = True
):
    """Update the status of a single task file.
    
    Args:
        file_path: Path to the task file
        note: Parsed note object
        status: New status value
        text: Optional text to append
        notes_dir: Path to notes directory
        display: Whether to display status update
    """
    # Validate: task groups cannot be marked done/dropped if children are incomplete
    if status in ("done", "dropped"):
        runner = MaintenanceRunner(notes_dir)
        task_name = note.path.stem
        incomplete = runner.get_incomplete_tasks(task_name)
        
        if incomplete:
            raise ValidationError(
                f"Cannot mark as {status} - has incomplete subtasks: {', '.join(incomplete)}"
            )

    # Load and update frontmatter
    post = frontmatter.load(file_path)

    if 'status' not in post.metadata:
        raise ValidationError("Could not find status field in frontmatter")

    old_status = post.get('status', 'none')
    post['status'] = status

    # If status is waiting, add a due date of 1 day
    if status == "waiting":
        due_date = (datetime.now() + timedelta(days=1)).strftime(DATE_TIME)
        post['due'] = due_date

    # Append text if provided
    if text:
        text_str = " ".join(text)
        post.content = post.content.rstrip() + f"\n{text_str}"

    with open(file_path, 'wb') as f:
        frontmatter.dump(post, f, sort_keys=False)

    # Run sync for immediate feedback (for single file) or batch (for bulk)
    if display:
        runner = MaintenanceRunner(notes_dir)
        runner.sync([str(file_path)])

        # Status display
        symbol = STATUS_SYMBOLS.get(status, "")
        click.echo(f"{symbol} {note.title}: {old_status} → {click.style(status, bold=True)}")
        
        if text:
            click.echo(f"  Added note: {' '.join(text)}")


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
    from ..utils import parse_checklist_items, remove_checklist_items

    notes_dir = get_notes_dir()

    # Remove .md extension if present
    if name.endswith('.md'):
        name = name[:-3]

    # Use fuzzy matching to resolve task name with focus prioritization
    focused = get_focused_project()
    result = resolve_file_fuzzy(name, include_archived=False, focused_project=focused)

    if result is None:
        return  # User cancelled

    stem, is_archived = result
    task_file = get_file_path(stem, is_archived)

    # Parse the task file
    post = frontmatter.load(task_file)

    # Verify it's a task
    if post.get('type') != 'task':
        raise ValidationError(f"File is not a task: {task_file}")

    # Extract checklist items from content
    checklist_items = parse_checklist_items(post.content)

    if not checklist_items:
        raise ValidationError(
            f"No checklist items found in {task_file.name}. "
            "Add unchecked items like '- [ ] subtask-name' to the Description section."
        )

    # Get the task stem (filename without .md)
    task_stem = task_file.stem

    # Determine parent info
    parent = post.get('parent')
    if not parent:
        raise ValidationError(f"Task has no parent field: {task_file}")

    log_info(click.style(f"Expanding {task_stem} into {len(checklist_items)} subtasks...", fg="cyan"))

    # Create subtask files
    template = get_template("task")
    created_files = []

    for task_name, task_status, task_text in checklist_items:
        # Shorten to max 6 words for filename and title
        words = task_name.split()[:6]
        shortened_name = '_'.join(words)
        # Replace characters that can break filenames: / { ( \ ) } , and others
        # Note: periods are preserved (e.g., v1.2.3, config.yaml)
        safe_name = re.sub(r'[,/{}()\\\[\]<>:;\'"?*|]', '_', shortened_name)
        # Truncate to avoid exceeding filesystem filename limits (max 255 chars)
        # Calculate max safe_name length: 255 - len(task_stem) - len('.') - len('.md')
        max_filename_len = 255
        max_safe_name_len = max_filename_len - len(task_stem) - 1 - 3  # -1 for '.', -3 for '.md'
        max_safe_name_len = max(20, max_safe_name_len)  # Ensure at least 20 chars for safe_name
        if len(safe_name) > max_safe_name_len:
            safe_name = safe_name[:max_safe_name_len]
        subtask_filename = f"{task_stem}.{safe_name}.md"
        subtask_path = notes_dir / subtask_filename

        if subtask_path.exists():
            click.echo(f"Warning: {subtask_filename} already exists, skipping")
            continue

        # Use shortened name (max 6 words) as the task title
        short_title = ' '.join(words)

        # Render subtask content with task as parent, using shortened title
        # and passing the full task text as message to include in body
        subtask_content = render_template(
            template,
            safe_name,
            parent=task_stem,
            parent_title=format_title(task_stem.split('.')[-1]),
            message=task_text,
        )

        # Parse the rendered content and set the status from checklist
        subtask_post = frontmatter.loads(subtask_content)
        subtask_post['status'] = task_status
        subtask_post['title'] = short_title
        
        # Write subtask with correct status
        with open(subtask_path, 'wb') as f:
            frontmatter.dump(subtask_post, f, sort_keys=False)
        
        created_files.append((safe_name, subtask_filename, task_status))
        log_verbose(f"  Created {subtask_filename} (status: {task_status})")

    # Remove checklist items from original task content
    new_content = remove_checklist_items(post.content)
    post.content = new_content

    # Write updated task file
    with open(task_file, 'wb') as f:
        frontmatter.dump(post, f, sort_keys=False)

    # Add subtask links to the task file (now acting as group)
    for safe_name, subtask_filename, _ in created_files:
        add_task_to_project(task_file, safe_name, subtask_filename.replace('.md', ''))

    log_info(click.style(f"\nSuccess! Created {len(created_files)} subtasks under {task_stem}", fg="green"))
    for safe_name, filename, status in created_files:
        log_info(f"  - {filename} (status: {status})")


@cli.command()
@click.argument("query")
@require_init
def link(query: str):
    """Print a [Title](stem.md) link for a note. Suitable for piping.

    \b
    Examples:
      cor link myproject                 # [My Project](myproject.md)
      cor link myproject.task1           # [Task 1](myproject.task1.md)
      cor link "task" | pbcopy          # Copy to clipboard
    """
    from ..core.notes import parse_note

    notes_dir = get_notes_dir()
    result = resolve_file_fuzzy(query, include_archived=True)
    if result is None:
        sys.exit(1)

    stem, in_archive = result
    note_file = notes_dir / f"{stem}.md"
    if not note_file.exists():
        note_file = notes_dir / "archive" / f"{stem}.md"

    if not note_file.exists():
        click.echo(f"No note found for '{query}'", err=True)
        sys.exit(1)

    note = parse_note(note_file)
    title = note.title if note and note.title else stem
    click.echo(f"[{title}]({stem}.md)", nl=False)
