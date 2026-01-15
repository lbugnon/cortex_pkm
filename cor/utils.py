"""Utility functions for Cortex CLI."""

import functools
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import click
from dateparser.search import search_dates

from .config import get_vault_path, get_verbosity
from .schema import DATE_TIME


def require_init(f):
    """Decorator that ensures vault is initialized before running command."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        notes_dir = get_vault_path()
        if not (notes_dir / "root.md").exists():
            raise click.ClickException("Not initialized. Run 'cor init' first.")
        return f(*args, **kwargs)
    return wrapper


def get_notes_dir() -> Path:
    """Get the current notes directory."""
    return get_vault_path()


# --- Path hierarchy utilities ---

def get_parent_name(stem: str) -> str | None:
    """Get parent from hierarchy (project.group.task -> project.group).

    Returns None if no parent (single-part name like 'project').
    """
    parts = stem.split(".")
    return ".".join(parts[:-1]) if len(parts) >= 2 else None


def get_root_project(stem: str) -> str:
    """Get root project name (project.group.task -> project)."""
    return stem.split(".")[0]


def get_hierarchy_depth(stem: str) -> int:
    """Get depth in hierarchy (project=1, project.task=2, project.group.task=3)."""
    return len(stem.split("."))


def get_templates_dir() -> Path:
    """Get the templates directory."""
    return get_vault_path() / "templates"


def get_projects() -> list[str]:
    """Get list of project names (files without dots in stem)."""
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []
    projects = []
    for p in notes_dir.glob("*.md"):
        # Projects have no dots in stem and aren't special files
        if "." not in p.stem and p.stem not in ("root", "backlog"):
            projects.append(p.stem)
    return sorted(projects)


def get_task_groups(project: str) -> list[str]:
    """Get list of task group names for a project (project.group.md files)."""
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []
    groups = []
    for p in notes_dir.glob(f"{project}.*.md"):
        parts = p.stem.split(".")
        # Task groups have exactly 2 parts: project.group
        if len(parts) == 2:
            groups.append(parts[1])
    return sorted(groups)


def get_project_tasks(project: str) -> list[str]:
    """Get list of direct task names for a project (project.task.md files, not in groups)."""
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []
    tasks = []
    for p in notes_dir.glob(f"{project}.*.md"):
        parts = p.stem.split(".")
        # Direct tasks have exactly 2 parts: project.task
        if len(parts) == 2:
            tasks.append(parts[1])
    return sorted(tasks)


def get_all_notes() -> list[str]:
    """Get list of all note file stems (projects + notes, excluding special files)."""
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []
    notes = []
    for p in notes_dir.glob("*.md"):
        if p.stem not in ("root", "backlog"):
            notes.append(p.stem)
    return sorted(notes)


def get_template(template_type: str) -> str:
    """Read a template file and return its contents."""
    import click
    template_path = get_templates_dir() / f"{template_type}.md"
    if not template_path.exists():
        raise click.ClickException(f"Template not found: {template_path}")
    return template_path.read_text()


def format_time_ago(ref_time: datetime) -> str:
    """Format time difference as human-readable string.

    - Less than 1 hour: shows minutes (e.g., "45m ago")
    - Less than 1 day: shows hours (e.g., "5h ago")
    - 1 day or more: shows days (e.g., "3d ago")
    """
    now = datetime.now()
    diff = now - ref_time
    total_seconds = diff.total_seconds()

    if total_seconds < 3600:  # Less than 1 hour
        minutes = int(total_seconds / 60)
        return f"{minutes}m ago" if minutes > 0 else "just now"
    elif total_seconds < 86400:  # Less than 1 day
        hours = int(total_seconds / 3600)
        return f"{hours}h ago"
    else:
        days = diff.days
        return f"{days}d ago"


def format_title(name: str) -> str:
    """Format name as title: underscores become spaces, capitalize first letter.

    Examples: "my_cool_task" -> "My cool task", "fix-bug" -> "Fix-bug"
    """
    title = name.replace("_", " ")
    return title[0].upper() + title[1:] if title else title


def render_template(
    template: str, name: str, parent: str | None = None, parent_title: str | None = None,
    message: str | None = None
) -> str:
    """Substitute placeholders in template."""
    now = datetime.now().strftime(DATE_TIME)
    
    # Generate parent link if parent exists
    parent_link = ""
    if parent and parent_title:
        parent_link = f"[< {parent_title}]({parent})"
    
    content = template.format(
        date=now,
        name=format_title(name),
        parent=parent or "",
        parent_title=parent_title or "",
        parent_link=parent_link,
    )
    # If message provided, add it to the Description section
    if message:
        content = content.replace("## Description\n", f"## Description\n\n{message}\n")
        content = content.replace("## Goal\n", f"## Goal\n\n{message}\n")
    return content


def is_vscode_terminal() -> bool:
    """Check if running inside VSCode's integrated terminal."""
    return (
        os.environ.get("TERM_PROGRAM") == "vscode" or
        "VSCODE_GIT_IPC_HANDLE" in os.environ
    )


def open_in_editor(filepath: Path):
    """Open file in appropriate editor based on environment.

    - In VSCode terminal: opens with `code` command
    - In regular terminal: opens with $EDITOR
    """
    if is_vscode_terminal():
        # Use VSCode's code command
        subprocess.call(["code", str(filepath)])
    else:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nvim"
        subprocess.call([editor, str(filepath)])


def add_task_to_project(project_path: Path, task_name: str, task_filename: str):
    """Add a task entry to the project's Tasks section."""
    if not project_path.exists():
        return

    content = project_path.read_text()
    task_entry = f"- [ ] [{format_title(task_name)}]({task_filename})"

    # Find Tasks section and add entry
    if "## Tasks" in content:
        lines = content.split("\n")
        new_lines = []
        in_tasks = False
        added = False

        for line in lines:
            new_lines.append(line)
            if line.strip() == "## Tasks":
                in_tasks = True
            elif in_tasks and not added:
                # Skip comment line
                if line.strip().startswith("<!--"):
                    continue
                # Add task after section header (and any comment)
                new_lines.append(task_entry)
                added = True
                in_tasks = False

        if not added:
            # Tasks section exists but empty, append at end
            new_lines.append(task_entry)

        project_path.write_text("\n".join(new_lines)+"\n")
    else:
        # No Tasks section, add one
        content += f"\n## Tasks\n{task_entry}\n"
        project_path.write_text(content)


# --- Verbosity utilities ---

def log_info(message: str, min_level: int = 1) -> None:
    """Print info message if verbosity >= min_level.

    Args:
        message: Message to print
        min_level: Minimum verbosity level to show (default: 1 for normal output)
    """
    if get_verbosity() >= min_level:
        click.echo(message)


def log_verbose(message: str) -> None:
    """Print verbose message (verbosity level 2)."""
    log_info(message, min_level=2)


def log_debug(message: str) -> None:
    """Print debug message (verbosity level 3)."""
    log_info(message, min_level=3)


def log_error(message: str) -> None:
    """Print error message (always shown)."""
    click.secho(message, fg="red", err=True)


def parse_natural_language_text(text: str) -> tuple[str, datetime | None, list[str]]:
    """Parse natural language text for due dates and tags.
    
    Detects:
    - Due dates: "due <date>" or "due: <date>" where <date> can be natural language
    - Tags: "tag <name>" or "tag: <name>" or multiple "tag <name1> <name2>"
    
    Args:
        text: Input text potentially containing due dates and tags
        
    Returns:
        Tuple of (cleaned_text, due_date, tags) where:
        - cleaned_text: text with due/tag specifications removed
        - due_date: parsed datetime object or None
        - tags: list of tag names
        
    Examples:
        >>> parse_natural_language_text("finish the pipeline due next friday")
        ('finish the pipeline', datetime(...), [])
        >>> parse_natural_language_text("fix bug tag urgent ml")
        ('fix bug', None, ['urgent', 'ml'])
        >>> parse_natural_language_text("complete task due tomorrow tag:urgent")
        ('complete task', datetime(...), ['urgent'])
    """
    if not text:
        return text, None, []
    
    due_date = None
    tags = []
    cleaned_text = text
    
    # Pattern to match "due <date>" or "due: <date>"
    # Regex explanation:
    # - \bdue:?\s+ : Match "due" or "due:" followed by whitespace (word boundary before "due")
    # - (.+?) : Capture the date text (non-greedy)
    # - (?=\s+tag(?:\b|:)|$) : Look ahead for "tag" keyword or end of string (don't capture)
    due_pattern = r'\bdue:?\s+(.+?)(?=\s+tag(?:\b|:)|$)'
    due_match = re.search(due_pattern, cleaned_text, re.IGNORECASE)
    
    if due_match:
        due_text = due_match.group(1).strip()
        # Parse the date using dateparser's search_dates which is better at finding dates
        result = search_dates(
            due_text,
            settings={
                'PREFER_DATES_FROM': 'future',
                'RETURN_AS_TIMEZONE_AWARE': False,
            }
        )
        if result:
            # search_dates returns a list of tuples (date_string, datetime)
            # Take the first match
            due_date = result[0][1]
            # Remove the entire due specification from text
            cleaned_text = cleaned_text[:due_match.start()] + cleaned_text[due_match.end():]
            cleaned_text = cleaned_text.strip()
    
    # Pattern to match "tag <tag1> <tag2> ..." or "tag: <tag1> <tag2> ..."
    # Regex explanation:
    # - \btag:?\s+ : Match "tag" or "tag:" followed by whitespace (word boundary before "tag")
    # - (.+?) : Capture the tag text (non-greedy)
    # - (?=\s+due(?:\b|:)|$) : Look ahead for "due" keyword or end of string (don't capture)
    tag_pattern = r'\btag:?\s+(.+?)(?=\s+due(?:\b|:)|$)'
    tag_match = re.search(tag_pattern, cleaned_text, re.IGNORECASE)
    
    if tag_match:
        tag_text = tag_match.group(1).strip()
        # Split by spaces to get individual tags
        tags = [t.strip() for t in tag_text.split() if t.strip()]
        # Remove the entire tag specification from text
        cleaned_text = cleaned_text[:tag_match.start()] + cleaned_text[tag_match.end():]
        cleaned_text = cleaned_text.strip()
    
    return cleaned_text, due_date, tags

