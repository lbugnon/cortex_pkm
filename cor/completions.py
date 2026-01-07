"""Shell completion functions for Cortex CLI."""

import os

from click.shell_completion import CompletionItem

from .schema import VALID_TASK_STATUS
from .utils import (
    get_notes_dir,
    get_projects,
    get_task_groups,
    get_project_tasks,
    get_all_notes,
)


def complete_name(ctx, param, incomplete: str) -> list:
    """Shell completion for task/note names with project prefix."""
    # Get note_type from context
    note_type = ctx.params.get("note_type", "")

    # Only suggest project prefixes for task/note types
    if note_type not in ("task", "note"):
        return []

    parts = incomplete.split(".")

    # No dot yet: suggest parent prefixes
    if len(parts) == 1:
        # For tasks: only projects (no dots in name)
        # For notes: all notes (projects + existing notes) can be parents
        if note_type == "task":
            parents = get_projects()
            help_text = "Tasks under {p}"
        else:
            parents = get_all_notes()
            help_text = "Notes under {p}"

        return [
            CompletionItem(f"{p}.", help=help_text.format(p=p))
            for p in parents
            if not incomplete or p.startswith(incomplete)
        ]

    # One dot (project.): suggest task groups if any exist
    if len(parts) == 2:
        project = parts[0]
        group_prefix = parts[1]
        groups = get_task_groups(project)
        if groups:
            return [
                CompletionItem(f"{project}.{g}.", help=f"Tasks in {g}")
                for g in groups
                if not group_prefix or g.startswith(group_prefix)
            ]

    return []


def complete_project(ctx, param, incomplete: str) -> list:
    """Shell completion for project names."""
    projects = get_projects()
    return [
        CompletionItem(p, help=f"Project {p}")
        for p in projects
        if not incomplete or p.startswith(incomplete)
    ]


def complete_existing_name(ctx, param, incomplete: str) -> list:
    """Shell completion for existing file names (projects and tasks).

    Uses prefix matching first, falls back to fuzzy matching if no prefix matches.
    """
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []

    completions = []
    archive_dir = notes_dir / "archive"

    # Check if -a/--archived flag is set
    include_archived = ctx.params.get("archived", False)

    # Check if incomplete starts with "archive/"
    is_archive_path = incomplete.startswith("archive/")
    search_stem = incomplete[8:] if is_archive_path else incomplete

    # Get all note files from main directory
    if not is_archive_path:
        for path in notes_dir.glob("*.md"):
            if path.stem not in ("root", "backlog") and not path.name.startswith("."):
                if not search_stem or path.stem.startswith(search_stem):
                    completions.append(CompletionItem(path.stem))

    # Also include archived files only if -a flag is set or user typed "archive/"
    if (include_archived or is_archive_path) and archive_dir.exists():
        for path in archive_dir.glob("*.md"):
            if not search_stem or path.stem.startswith(search_stem):
                completions.append(CompletionItem(f"archive/{path.stem}", help="(archived)"))

    # Fuzzy fallback: if no prefix matches and user typed 2+ chars, try fuzzy
    if not completions and len(search_stem) >= 2:
        from .fuzzy import fuzzy_match, get_all_file_stems

        candidates = get_all_file_stems(include_archived=include_archived)
        fuzzy_results = fuzzy_match(search_stem, candidates, limit=5, score_cutoff=50)
        
        # For shell completion, only show results within 10 points of the top score
        # This helps the shell find a common prefix for autocomplete
        if fuzzy_results:
            top_score = fuzzy_results[0][2]
            fuzzy_results = [r for r in fuzzy_results if r[2] >= top_score - 10]
            # Collapse 100%-score ties to shortest unless disabled (default disabled)
            collapse_100 = os.environ.get("COR_COMPLETE_COLLAPSE_100", "0").lower() not in {"0", "false", "no"}
            if collapse_100 and top_score == 100:
                top_ties = [r for r in fuzzy_results if r[2] == top_score]
                if len(top_ties) > 1:
                    fuzzy_results = [fuzzy_results[0]]
        
        for stem, is_archived, score in fuzzy_results:
            if is_archived:
                completions.append(
                    CompletionItem(f"archive/{stem}", help=f"(fuzzy {score}%)")
                )
            else:
                completions.append(CompletionItem(stem, help=f"(fuzzy {score}%)"))

    return completions


def complete_group_project(ctx, param, incomplete: str) -> list:
    """Shell completion for group command: project.groupname format."""
    parts = incomplete.split(".")

    if len(parts) == 1:
        # No dot yet: suggest projects
        return [
            CompletionItem(f"{p}.", help=f"Create group under {p}")
            for p in get_projects()
            if not incomplete or p.startswith(incomplete)
        ]

    # After dot: user is typing group name, no completion
    return []


def complete_project_tasks(ctx, param, incomplete: str) -> list:
    """Shell completion for task names belonging to the project from group argument."""
    # Get the group argument (project.groupname)
    group_arg = ctx.params.get("group", "")
    if not group_arg or "." not in group_arg:
        return []

    project = group_arg.split(".")[0]
    tasks = get_project_tasks(project)

    return [
        CompletionItem(t, help=f"{project}.{t}.md")
        for t in tasks
        if not incomplete or t.startswith(incomplete)
    ]


def complete_task_name(ctx, param, incomplete: str) -> list:
    """Shell completion for task names (type: task in frontmatter)."""
    from .parser import parse_note
    from .fuzzy import fuzzy_match

    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []

    tasks = []

    # Collect all task file stems
    for path in notes_dir.glob("*.md"):
        if path.stem in ("root", "backlog"):
            continue
        note = parse_note(path)
        if note and note.note_type == "task":
            tasks.append(path.stem)

    # Prefix matches first
    prefix_matches = [
        CompletionItem(stem)
        for stem in tasks
        if not incomplete or stem.startswith(incomplete)
    ]

    # If we found prefix matches or the input is too short, return
    if prefix_matches or len(incomplete) < 2:
        return prefix_matches

    # Fuzzy fallback: use new fuzzy sorter (score desc, length asc) and filter near top
    candidates = [(stem, False) for stem in tasks]
    fuzzy_results = fuzzy_match(incomplete, candidates, limit=5, score_cutoff=50)

    if fuzzy_results:
        top_score = fuzzy_results[0][2]
        fuzzy_results = [r for r in fuzzy_results if r[2] >= top_score - 10]
        # Collapse 100%-score ties to shortest unless disabled (default disabled)
        collapse_100 = os.environ.get("COR_COMPLETE_COLLAPSE_100", "0").lower() not in {"0", "false", "no"}
        if collapse_100 and top_score == 100:
            top_ties = [r for r in fuzzy_results if r[2] == top_score]
            if len(top_ties) > 1:
                fuzzy_results = [fuzzy_results[0]]

    return [CompletionItem(stem, help=f"(fuzzy {score}%)") for stem, _, score in fuzzy_results]


def complete_task_status(ctx, param, incomplete: str) -> list:
    """Shell completion for task status values."""
    return [
        CompletionItem(s)
        for s in sorted(VALID_TASK_STATUS)
        if not incomplete or s.startswith(incomplete)
    ]


def complete_new_parent(ctx, param, incomplete: str) -> list:
    """Completion for target parent in rename: suggest projects and existing groups.

    - If typing a project: suggest projects
    - If typing project.: suggest existing groups for that project
    """
    projects = get_projects()
    parts = incomplete.split(".")

    # No dot yet: suggest projects
    if len(parts) == 1:
        return [
            CompletionItem(p, help=f"Project {p}")
            for p in projects
            if not incomplete or p.startswith(incomplete)
        ]

    # After dot: suggest groups under the given project
    project = parts[0]
    group_prefix = parts[1] if len(parts) > 1 else ""
    if project in projects:
        groups = get_task_groups(project)
        return [
            CompletionItem(f"{project}.{g}", help=f"Group {g} in {project}")
            for g in groups
            if not group_prefix or g.startswith(group_prefix)
        ]

    return []
