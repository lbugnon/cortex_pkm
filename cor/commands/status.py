"""Status and reporting commands for Cortex CLI."""

from datetime import datetime, date, timedelta
import re

import click

from ..completions import complete_project
from ..parser import find_notes
from ..schema import STATUS_SYMBOLS
from ..utils import get_notes_dir, format_time_ago, require_init, format_title

# Shared color mappings for all tree views
TASK_COLORS = {
    "done": "green",
    "active": "cyan",
    "blocked": "red",
    "dropped": "magenta",
    "todo": "white",
    "waiting": "yellow",
}

PROJECT_COLORS = {
    "planning": "blue",
    "active": "green",
    "paused": "yellow",
    "done": "bright_black",
}

# Status sort order for tree display
STATUS_ORDER = {"blocked": 0, "active": 1, "waiting": 2, "todo": 3, "dropped": 4, "done": 5}


def _update_root_section(notes_dir, section: str, body: str) -> None:
    """Replace a section in root.md with new body content."""
    root_path = notes_dir / "root.md"
    if not root_path.exists():
        return

    content = root_path.read_text()
    body_clean = body.lstrip("\n").rstrip() + "\n"
    pattern = rf"(## {re.escape(section)}\n)(.*?)(\n## |\Z)"
    match = re.search(pattern, content, flags=re.S)

    if match:
        before = content[:match.start()]
        after = content[match.end():]
        delimiter = match.group(3)
        new_section = f"{match.group(1)}\n{body_clean}"
        if delimiter.startswith("\n## "):
            new_content = before + new_section + delimiter + after
        else:
            new_content = before + new_section
    else:
        new_content = content.rstrip() + f"\n\n## {section}\n\n{body_clean}"

    root_path.write_text(new_content)


def show_tree(
    parent_name: str,
    tasks_by_parent: dict,
    prefix: str = "",
    filter_fn=None,
    sort_fn=None,
    render_fn=None,
    show_separators: bool = False,
    separator_transitions: list = None,
    capture: list | None = None,
):
    """
    Unified tree rendering function.

    Args:
        parent_name: The parent node to render children of
        tasks_by_parent: Dict mapping parent names to list of child tasks
        prefix: Current indentation prefix string
        filter_fn: Optional function(task) -> bool to filter which tasks to show
        sort_fn: Optional function(tasks) -> sorted_tasks
        render_fn: Function(task) -> str to render task display (symbol + title)
        show_separators: Whether to show --- separators between status groups
        separator_transitions: List of (from_statuses, to_statuses) tuples for separators
    """
    if parent_name not in tasks_by_parent:
        return

    tasks = tasks_by_parent[parent_name]

    # Apply filter if provided
    if filter_fn:
        tasks = [t for t in tasks if filter_fn(t)]

    if not tasks:
        return

    # Apply sorting if provided
    if sort_fn:
        tasks = sort_fn(tasks)

    # Default separator transitions
    if separator_transitions is None:
        separator_transitions = [
            (("blocked", "active", "waiting"), ("todo",)),
            (("todo",), ("dropped", "done")),
        ]

    prev_status = None
    for i, task in enumerate(tasks):
        is_last = i == len(tasks) - 1
        branch = "└── " if is_last else "├── "
        child_prefix = prefix + ("    " if is_last else "│   ")

        # Check for separator
        if show_separators and prev_status is not None:
            for from_statuses, to_statuses in separator_transitions:
                if prev_status in from_statuses and task.status in to_statuses:
                    sep_prefix = prefix + "│"
                    sep_line = click.style(f"{sep_prefix}   ---", dim=True)
                    click.echo(sep_line)
                    if capture is not None:
                        capture.append(click.unstyle(sep_line))
                    break

        # Render the task
        if render_fn:
            task_display = render_fn(task)
        else:
            symbol = STATUS_SYMBOLS.get(task.status, "[ ]")
            color = TASK_COLORS.get(task.status, "white")
            task_display = f"{click.style(symbol, fg=color)} {task.title}"

        line = f"{prefix}{branch}{task_display}"
        click.echo(line)
        if capture is not None:
            capture.append(click.unstyle(line))

        # Recurse for children
        show_tree(
            task.path.stem,
            tasks_by_parent,
            child_prefix,
            filter_fn=filter_fn,
            sort_fn=sort_fn,
            render_fn=render_fn,
            show_separators=show_separators,
            separator_transitions=separator_transitions,
            capture=capture,
        )

        prev_status = task.status


def _group_by_project(tasks: list) -> dict:
    """Group tasks by their parent project."""
    from collections import OrderedDict
    groups = OrderedDict()
    for task in tasks:
        project = task.parent_project or task.path.stem
        groups.setdefault(project, []).append(task)
    return groups


def _print_section(title: str, tasks: list, color: str, formatter, limit: int, capture: list | None = None) -> bool:
    """Print section with tasks grouped by project. Returns True if printed."""
    if not tasks:
        return False

    heading = click.style(f"\n{title}", fg=color, bold=True)
    click.echo(heading)
    if capture is not None:
        capture.append(click.unstyle(heading))
    shown = 0
    groups = _group_by_project(tasks)

    for project, project_tasks in groups.items():
        project_display = format_title(project)
        if limit and shown >= limit:
            break
        project_line = f"  {project_display}"
        click.echo(project_line)
        if capture is not None:
            capture.append(click.unstyle(project_line))
        for task in project_tasks:
            if limit and shown >= limit:
                break
            symbol = STATUS_SYMBOLS.get(task.status, "[ ]")
            task_color = TASK_COLORS.get(task.status, "white")
            info = formatter(task)
            styled_symbol = click.style(symbol, fg=task_color)
            line = f"  └── {styled_symbol} {task.title}{info}"
            click.echo(line)
            if capture is not None:
                capture.append(click.unstyle(line))
            shown += 1

    remaining = len(tasks) - shown
    if remaining > 0:
        click.echo(click.style(f"  ... and {remaining} more", dim=True))
    return True


@click.command(short_help="Prioritized daily view of tasks")
@click.option("--limit", "-l", default=3, help="Max items per section (default: 3)")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all items (no limit)")
@require_init
def daily(limit: int, show_all: bool):
    """Show what needs attention today.

    \b
    Prioritized daily view:
    - Overdue items (fix first)
    - Stale waiting items (follow up)
    - Due today
    - In progress (continue)
    - High priority ready
    - Suggested next (from active projects)
    """
    notes_dir = get_notes_dir()
    root_lines: list[str] = []

    notes = find_notes(notes_dir)
    now = datetime.now()
    today = now.date()

    if show_all:
        limit = 0  # 0 means no limit

    # Build set of active project names
    active_projects = {n.path.stem for n in notes
                       if n.note_type == "project" and n.status == "active"}

    # Track shown items to avoid duplicates
    shown_paths = set()
    sections_printed = False

    # Helper to format overdue time
    def format_overdue(n):
        days = n.days_overdue
        if days == 0:
            return " (due today)"
        elif days == 1:
            return " (1d overdue)"
        else:
            return f" ({days}d overdue)"

    # 1. Overdue (tasks only, sorted by due date)
    overdue = [n for n in notes
               if n.is_overdue and n.note_type == "task"]
    overdue.sort(key=lambda n: n.due)
    if _print_section(
        "Overdue",
        overdue,
        "red",
        format_overdue,
        limit,
        capture=root_lines,
    ):
        sections_printed = True
        shown_paths.update(n.path for n in overdue[:limit or len(overdue)])

    # 2. Waiting stale (waiting status + stale)
    waiting_stale = [n for n in notes
                     if n.status == "waiting" and n.is_stale
                     and n.path not in shown_paths]
    waiting_stale.sort(key=lambda n: n.modified or datetime.min)
    if _print_section(
        "Waiting (stale)",
        waiting_stale,
        "yellow",
        lambda n: f" ({format_time_ago(n.modified)} since update)" if n.modified else "",
        limit,
        capture=root_lines,
    ):
        sections_printed = True
        shown_paths.update(n.path for n in waiting_stale[:limit or len(waiting_stale)])

    # 3. Due today
    due_today = [n for n in notes
                 if n.due and n.due == today
                 and n.status not in ("done", "dropped")
                 and n.path not in shown_paths]
    priority_order = {"high": 0, "medium": 1, "low": 2}
    due_today.sort(key=lambda n: priority_order.get(n.priority, 3))
    if _print_section(
        "Due Today",
        due_today,
        "cyan",
        lambda n: f" [{n.priority}]" if n.priority else "",
        limit,
        capture=root_lines,
    ):
        sections_printed = True
        shown_paths.update(n.path for n in due_today[:limit or len(due_today)])

    # 4. In Progress (active tasks)
    in_progress = [n for n in notes
                   if n.status == "active" and n.note_type == "task"
                   and n.path not in shown_paths]
    in_progress.sort(key=lambda n: n.modified or datetime.min)
    if _print_section(
        "In Progress",
        in_progress,
        "blue",
        lambda n: f" ({format_time_ago(n.modified)})" if n.modified else "",
        limit,
        capture=root_lines,
    ):
        sections_printed = True
        shown_paths.update(n.path for n in in_progress[:limit or len(in_progress)])

    # 5. High Priority Ready (high priority + todo)
    high_priority = [n for n in notes
                     if n.priority == "high"
                     and n.status == "todo"
                     and n.note_type == "task"
                     and n.path not in shown_paths]
    high_priority.sort(key=lambda n: n.created or datetime.min)
    if _print_section(
        "High Priority",
        high_priority,
        "magenta",
        lambda n: "",
        limit,
        capture=root_lines,
    ):
        sections_printed = True
        shown_paths.update(n.path for n in high_priority[:limit or len(high_priority)])

    # 6. Suggested Next (todo tasks in active projects)
    suggested = [n for n in notes
                 if n.status == "todo"
                 and n.note_type == "task"
                 and n.path not in shown_paths
                 and n.parent_project in active_projects]
    suggested.sort(key=lambda n: n.modified or datetime.min)
    if _print_section(
        "Suggested Next",
        suggested,
        "white",
        lambda n: "",
        limit,
        capture=root_lines,
    ):
        sections_printed = True

    if not sections_printed:
        line = click.style("\nAll clear! Nothing urgent for today.", fg="green")
        click.echo(line)
        root_lines.append(click.unstyle(line))

    click.echo()

    if root_lines:
        _update_root_section(notes_dir, "Daily", "\n".join(root_lines))


def _get_project_last_activity(project_name: str, all_notes: list) -> datetime | None:
    """Get the most recent modification date from a project's tasks/notes."""
    most_recent = None
    
    for note in all_notes:
        # Check if this note belongs to the project
        if note.parent_project == project_name and note.note_type in ("task", "note"):
            if note.modified:
                if most_recent is None or note.modified > most_recent:
                    most_recent = note.modified
    
    return most_recent


@click.command(short_help="List projects with status and activity")
@click.option("--all", "-a", "show_all", is_flag=True, help="Include archived/done projects")
@require_init
def projects(show_all: bool):
    """List active projects with status and age.

    \b
    Details:
    - Sorted by last activity (most recent task/note update)
    - Color-coded: planning (blue), active (green), paused (yellow)
    - Stale projects (>14 days) highlighted in red
    - Use -a to include done/archived projects
    """
    notes_dir = get_notes_dir()
    root_lines: list[str] = []

    notes = find_notes(notes_dir)

    # Include archived projects if -a flag is set
    if show_all:
        archive_dir = notes_dir / "archive"
        if archive_dir.exists():
            notes.extend(find_notes(archive_dir))

    # Filter to projects only (exclude done unless show_all)
    if show_all:
        projects_list = [n for n in notes if n.note_type == "project"]
    else:
        projects_list = [
            n for n in notes
            if n.note_type == "project" and n.status != "done"
        ]

    if not projects_list:
        if show_all:
            click.echo("No projects found.")
        else:
            click.echo("No active projects found.")
        return

    # Sort by last activity from children (oldest first = needs attention)
    # Fall back to project's own modified date if no children
    # Handle None dates by placing them at the beginning (needs attention)
    def get_sort_key(proj):
        project_name = proj.path.stem
        last_activity = _get_project_last_activity(project_name, notes)
        return last_activity or proj.modified or datetime.min
    
    projects_list.sort(key=get_sort_key)

    header = click.style("\nProjects:", bold=True)
    click.echo(header)
    click.echo()
    root_lines.append(click.unstyle(header))

    for p in projects_list:
        # Use last activity from children, fall back to project modified date
        project_name = p.path.stem
        last_activity = _get_project_last_activity(project_name, notes)
        ref_date = last_activity or p.modified or p.created
        
        # Calculate time since modified
        age_str = format_time_ago(ref_date) if ref_date else "unknown"
        days_ago = (datetime.now() - ref_date).days if ref_date else 0

        # Determine color (stale overrides status color)
        is_stale = (days_ago > 7) and (p.status == "active")
        if is_stale:
            color = "red"
            status_display = f"{p.status or 'no status'} (stale)"
        else:
            color = PROJECT_COLORS.get(p.status, "white")
            status_display = p.status or "no status"

        # Format output
        status_styled = click.style(f"[{status_display}]", fg=color)
        age_styled = click.style(age_str, fg="red" if is_stale else "cyan")

        display_title = format_title(p.title)
        line = f"  {status_styled} {display_title} - {age_styled}"
        click.echo(line)
        root_lines.append(click.unstyle(line))

    click.echo()

    if root_lines:
        _update_root_section(notes_dir, "Projects", "\n".join(root_lines))


@click.command()
@click.option("--weeks", "-w", default=1, help="Number of weeks to look back (default: 1)")
@click.argument("projects", nargs=-1, shell_complete=complete_project)
@require_init
def weekly(weeks: int, projects: tuple):
    """Show weekly summary in tree format.

    Without project filter: shows completed tasks grouped by project.
    With project filter: shows full project tree (except TODO), ordered by status.

    Optionally filter by one or more projects:
      cor weekly project-a project-b
    """
    notes_dir = get_notes_dir()

    # Calculate date range
    now = datetime.now()
    start_date = now - timedelta(days=7 * weeks)

    # Week display range
    week_start = start_date.date()
    week_end = now.date()

    # Get all notes including archived
    notes = find_notes(notes_dir)
    archive_dir = notes_dir / "archive"
    if archive_dir.exists():
        notes.extend(find_notes(archive_dir))

    # Filter by projects if specified
    project_filter = set(projects) if projects else None

    # Build project data and task hierarchy
    # project_name -> {done: int, active: int, total: int, high_priority: [tasks]}
    project_data = {}
    completed_this_week = set()  # paths of tasks completed this week
    tasks_by_parent = {}  # parent_name -> [tasks]
    all_tasks = {}  # path.stem -> note

    for n in notes:
        if n.note_type != "task":
            continue

        project = n.parent_project or n.path.stem
        all_tasks[n.path.stem] = n

        # Track project stats
        if project not in project_data:
            project_data[project] = {"done": 0, "active": 0, "total": 0, "high_priority": []}

        project_data[project]["total"] += 1

        if n.status in ("done", "dropped"):
            project_data[project]["done"] += 1
            # Check if completed this period
            if n.modified and n.modified >= start_date:
                completed_this_week.add(n.path.stem)
        elif n.status in ("active", "waiting"):
            project_data[project]["active"] += 1

        # Track high priority tasks (not done/dropped)
        if n.priority == "high" and n.status not in ("done", "dropped"):
            project_data[project]["high_priority"].append(n)

        # Build parent -> children mapping
        parts = n.path.stem.split(".")
        if len(parts) >= 2:
            parent = ".".join(parts[:-1])
            tasks_by_parent.setdefault(parent, []).append(n)

    # Find projects with completed tasks this week
    projects_with_completed = set()
    for stem in completed_this_week:
        parts = stem.split(".")
        if parts:
            projects_with_completed.add(parts[0])

    # Print week header
    if weeks == 1:
        month_name = week_start.strftime("%b")
        header = f"Week of {month_name} {week_start.day}-{week_end.day}"
    else:
        header = f"Past {weeks} weeks ({week_start} to {week_end})"

    if project_filter:
        header += f" [{', '.join(sorted(format_title(p) for p in project_filter))}]"

    capture_lines: list[str] = []

    def emit(line: str = ""):
        click.echo(line)
        capture_lines.append(click.unstyle(line))

    emit(click.style(f"\n═══ {header} ═══", bold=True))

    # === Project-specific view: show full tree (except TODO) ===
    if project_filter:
        for project_name in sorted(project_filter):
            display_project = format_title(project_name)
            if project_name not in tasks_by_parent and project_name not in project_data:
                emit(click.style(f"\nProject '{display_project}' not found or has no tasks.", dim=True))
                continue

            stats = project_data.get(project_name, {"done": 0, "active": 0, "total": 0, "high_priority": []})
            done_count = stats["done"]
            active_count = stats["active"]
            total_count = stats["total"]

            # Project header with counters
            is_project_done = done_count == total_count and total_count > 0
            project_color = "green" if is_project_done else "cyan"

            counter_str = f"({done_count} done, {active_count} active, {total_count} total)"
            emit(click.style(display_project, fg=project_color, bold=True) + " " + click.style(counter_str, dim=True))

            # Sort: done/dropped first, then active/waiting, then blocked
            # Filter out TODO tasks
            weekly_status_order = {"done": 0, "dropped": 1, "active": 2, "waiting": 3, "blocked": 4, "todo": 99}

            def weekly_sort(tasks):
                return sorted(tasks, key=lambda t: (weekly_status_order.get(t.status, 5), t.path.stem))

            def weekly_filter(task):
                return task.status != "todo"

            def weekly_render(task):
                symbol = STATUS_SYMBOLS.get(task.status, "[ ]")
                color = TASK_COLORS.get(task.status, "white")
                priority_mark = click.style(" [HIGH]", fg="magenta", bold=True) if task.priority == "high" else ""
                return f"{click.style(symbol, fg=color)} {task.title}{priority_mark}"

            show_tree(
                project_name,
                tasks_by_parent,
                filter_fn=weekly_filter,
                sort_fn=weekly_sort,
                render_fn=weekly_render,
                capture=capture_lines,
            )

            # List high priority tasks separately if any
            high_priority = stats["high_priority"]
            if high_priority:
                emit()
                emit(click.style("  ⚡ High Priority:", fg="magenta", bold=True))
                for hp in high_priority:
                    status_str = click.style(f"[{hp.status}]", fg=TASK_COLORS.get(hp.status, "white"))
                    emit(f"    • {hp.title} {status_str}")

        emit()
        if capture_lines:
            _update_root_section(notes_dir, "Weekly", "\n".join(capture_lines))
        return

    # === Default view: show completed tasks this week ===
    if not projects_with_completed:
        emit(click.style("\nNo completed tasks this week.", dim=True))
        emit()
        if capture_lines:
            _update_root_section(notes_dir, "Weekly", "\n".join(capture_lines))
        return

    emit(click.style(f"\nCompleted: {len(completed_this_week)} tasks\n", fg="green", bold=True))

    def has_completed_descendant(parent_name: str) -> bool:
        """Check if parent has any completed descendants this week."""
        if parent_name in completed_this_week:
            return True
        for child in tasks_by_parent.get(parent_name, []):
            if has_completed_descendant(child.path.stem):
                return True
        return False

    def weekly_filter_completed(task):
        return has_completed_descendant(task.path.stem)

    def weekly_render_completed(task):
        if task.path.stem in completed_this_week:
            symbol = "[x]" if task.status == "done" else "[~]"
            color = TASK_COLORS.get(task.status, "white")
            return f"{click.style(symbol, fg=color)} {task.title}"
        else:
            # Group header (not completed, but has completed children)
            return click.style(task.title, dim=True)

    # Print each project
    for project_name in sorted(projects_with_completed):
        stats = project_data.get(project_name, {"done": 0, "active": 0, "total": 0, "high_priority": []})
        done_count = stats["done"]
        active_count = stats["active"]
        total_count = stats["total"]

        # Project is "done" if all tasks are done
        is_project_done = done_count == total_count and total_count > 0
        project_color = "green" if is_project_done else "cyan"

        # Project header with counters
        display_project = format_title(project_name)
        if is_project_done:
            suffix = click.style(" (done)", fg="green")
        else:
            counter_str = f"({done_count} done, {active_count} active, {total_count} total)"
            suffix = " " + click.style(counter_str, dim=True)

        emit(click.style(display_project, fg=project_color, bold=True) + suffix)

        show_tree(
            project_name,
            tasks_by_parent,
            filter_fn=weekly_filter_completed,
            render_fn=weekly_render_completed,
            capture=capture_lines,
        )
        emit()

    if capture_lines:
        _update_root_section(notes_dir, "Weekly", "\n".join(capture_lines))


@click.command(short_help="Show a project's task tree")
@click.argument("project", shell_complete=complete_project)
@require_init
def tree(project: str):
    """Show task tree for a project.

    Displays tasks in a tree view with [x] or [ ] indicating status.

    \b
    Example:
      cor tree myproject
    """
    notes_dir = get_notes_dir()

    project_path = notes_dir / f"{project}.md"
    if not project_path.exists():
        raise click.ClickException(f"Project not found: {project}")

    # Include both active notes and archived ones
    notes = find_notes(notes_dir)
    archive_dir = notes_dir / "archive"
    if archive_dir.exists():
        notes.extend(find_notes(archive_dir))

    # Find the project
    project_note = None
    for note in notes:
        if note.path.stem == project:
            project_note = note
            break

    if not project_note:
        raise click.ClickException(f"Could not parse project: {project}")

    # Build parent -> tasks mapping
    tasks_by_parent = {}
    for note in notes:
        if note.note_type == "task":
            parts = note.path.stem.split(".")
            if len(parts) >= 2 and parts[0] == project:
                parent = ".".join(parts[:-1])
                tasks_by_parent.setdefault(parent, []).append(note)

    # Print project header
    color = PROJECT_COLORS.get(project_note.status)
    click.echo(click.style(f"\n{project_note.title}", fg=color, bold=True))
    click.echo(click.style(f"({project_note.status or 'no status'})", dim=True))

    if project not in tasks_by_parent:
        click.echo("  No tasks found.")
    else:
        # Sort function: by status order, then by name
        def sort_tasks(tasks):
            return sorted(tasks, key=lambda t: (STATUS_ORDER.get(t.status, 3), t.path.stem))

        show_tree(
            project,
            tasks_by_parent,
            sort_fn=sort_tasks,
            show_separators=True,
        )


@click.command(short_help="Weekly review summary and insights")
@click.option("--weeks", "-w", default=1, help="Number of weeks to look back (default: 1)")
@require_init
def review(weeks: int):
    """Weekly review assistant.

    \b
    Summarizes:
    - What moved (status changes, completed items)
    - What's stale (needs attention)
    - What's upcoming (due dates, priorities)

    \b
    Use this for weekly planning and reflection.
    """
    notes_dir = get_notes_dir()

    now = datetime.now()
    start_date = now - timedelta(days=7 * weeks)
    end_of_week = now + timedelta(days=7)

    # Get all notes including archived
    notes = find_notes(notes_dir)
    archive_dir = notes_dir / "archive"
    if archive_dir.exists():
        notes.extend(find_notes(archive_dir))

    # Categorize
    completed = []
    created = []
    active = []
    blocked = []
    stale = []
    due_soon = []
    overdue = []
    high_priority = []

    for n in notes:
        # Skip special files
        if n.note_type in ("backlog", "root"):
            continue

        # Completed this period
        if n.status in ("done", "dropped") and n.modified and n.modified >= start_date:
            completed.append(n)

        # Created this period
        if n.created and n.created >= start_date:
            created.append(n)

        # Currently active
        if n.status == "active":
            active.append(n)

        # Currently blocked
        if n.status == "blocked":
            blocked.append(n)

        # Stale items (active but not touched)
        if n.is_stale:
            stale.append(n)

        # Due soon
        if n.due and n.due <= end_of_week and n.status not in ("done", "dropped"):
            if n.is_overdue:
                overdue.append(n)
            else:
                due_soon.append(n)

        # High priority
        if n.priority == "high" and n.status not in ("done", "dropped"):
            high_priority.append(n)

    # Print review
    period_str = "this week" if weeks == 1 else f"past {weeks} weeks"
    click.echo(click.style(f"\n═══ Weekly Review ({period_str}) ═══\n", bold=True))

    # Summary stats
    click.echo(click.style("📊 Summary", bold=True))
    click.echo(f"  Completed: {click.style(str(len(completed)), fg='green', bold=True)}")
    click.echo(f"  Created:   {click.style(str(len(created)), fg='cyan', bold=True)}")
    click.echo(f"  Active:    {click.style(str(len(active)), fg='blue', bold=True)}")
    click.echo(f"  Blocked:   {click.style(str(len(blocked)), fg='red', bold=True)}")
    click.echo()

    # What moved (completed)
    if completed:
        click.echo(click.style("✅ Completed", fg="green", bold=True))
        for n in sorted(completed, key=lambda x: x.modified or date.min, reverse=True):
            symbol = "✓" if n.status == "done" else "~"
            type_tag = f"[{n.note_type}]" if n.note_type != "task" else ""
            click.echo(f"  {symbol} {n.title} {type_tag}")
        click.echo()

    # What needs attention
    if overdue:
        click.echo(click.style("🚨 Overdue", fg="red", bold=True))
        for n in sorted(overdue, key=lambda x: x.due or date.min):
            days = (now.date() - n.due).days
            if days == 1:
                click.echo(f"  • {n.title} (1d overdue)")
            else:
                click.echo(f"  • {n.title} ({days}d overdue)")
        click.echo()

    if blocked:
        click.echo(click.style("🔒 Blocked", fg="red", bold=True))
        for n in blocked:
            time_str = format_time_ago(n.modified) if n.modified else ""
            click.echo(f"  • {n.title} (blocked {time_str})" if time_str else f"  • {n.title}")
        click.echo()

    if stale:
        click.echo(click.style("💤 Stale (needs attention)", fg="yellow", bold=True))
        for n in sorted(stale, key=lambda x: x.modified or datetime.min):
            time_str = format_time_ago(n.modified) if n.modified else ""
            click.echo(f"  • {n.title} ({time_str})" if time_str else f"  • {n.title}")
        click.echo()

    # What's upcoming
    if due_soon:
        click.echo(click.style("📅 Due this week", fg="cyan", bold=True))
        for n in sorted(due_soon, key=lambda x: x.due or datetime.max):
            days = (n.due - now.date()).days
            day_str = "today" if days == 0 else f"in {days}d"
            click.echo(f"  • {n.title} ({day_str})")
        click.echo()

    if high_priority:
        click.echo(click.style("⚡ High Priority", fg="magenta", bold=True))
        for n in high_priority:
            status_str = f"[{n.status}]" if n.status else ""
            click.echo(f"  • {n.title} {status_str}")
        click.echo()

    # Currently active work
    if active:
        click.echo(click.style("🔧 Currently Active", fg="blue", bold=True))
        for n in sorted(active, key=lambda x: x.modified or datetime.min, reverse=True):
            time_str = format_time_ago(n.modified) if n.modified else ""
            type_tag = f"[{n.note_type}]" if n.note_type != "task" else ""
            click.echo(f"  • {n.title} ({time_str}) {type_tag}" if time_str else f"  • {n.title} {type_tag}")
        click.echo()

    # Recommendations
    click.echo(click.style("💡 Recommendations", bold=True))
    recommendations = []

    if overdue:
        recommendations.append(f"Address {len(overdue)} overdue item(s)")
    if blocked:
        recommendations.append(f"Unblock {len(blocked)} item(s)")
    if stale:
        recommendations.append(f"Review {len(stale)} stale item(s) - update or pause them")
    if len(active) > 5:
        recommendations.append(f"Consider focusing - {len(active)} active items is a lot")
    if not active and not due_soon:
        recommendations.append("No active work - time to start something new?")

    if recommendations:
        for rec in recommendations:
            click.echo(f"  → {rec}")
    else:
        click.echo(click.style("  All looking good! 🎉", fg="green"))

    click.echo()
