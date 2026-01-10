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
from .search.completion import complete_files_with_fuzzy, complete_filtered_with_fuzzy
from bibtexparser import loads as bibtex_loads
from .bibtex import get_bib_path


def complete_ref(ctx, param, incomplete: str) -> list:
    """Shell completion for references by citekey, author, or title.

    Returns citekeys as completion values with helpful context.
    """
    from click.shell_completion import CompletionItem
    from .search.fuzzy import fuzzy_match
    
    notes_dir = get_notes_dir()
    bib_path = get_bib_path(notes_dir)
    if not bib_path.exists():
        return []

    db = bibtex_loads(bib_path.read_text())
    
    inc = (incomplete or "").strip().lower()
    entries = getattr(db, "entries", [])
    
    if not entries:
        return []

    items = []
    for e in entries:
        cid = (e.get("ID") or "").strip()
        if not cid:
            continue
        title = (e.get("title") or "").strip()
        author = (e.get("author") or "").strip()
        year = (e.get("year") or "").strip()

        # Build authors short string (Last et al., Year)
        authors_list = [a.strip() for a in author.split(" and ") if a.strip()]
        first_last = authors_list[0].split(",")[0].strip() if authors_list else "Unknown"
        if len(authors_list) > 1:
            short_auth = f"{first_last} et al."
        else:
            short_auth = first_last

        help_text = f"{short_auth} {year} — {title[:80]}".strip()

        # Extract last names for prefix matching
        last_names = [part.split(",")[0].strip().lower() for part in authors_list]

        items.append({
            "id": cid,
            "id_lower": cid.lower(),
            "title": title,
            "authors": authors_list,
            "last_names": last_names,
            "year": year,
            "help": help_text,
        })

    # 1) Prefix matches: citekey or author last name
    prefix_matches = []
    if inc:
        for it in items:
            if it["id_lower"].startswith(inc) or any(ln.startswith(inc) for ln in it["last_names"]):
                prefix_matches.append(CompletionItem(it["id"], help=it["help"]))

    # If we have prefix matches, return them
    if prefix_matches:
        return prefix_matches[:10]
    
    # Return all items if no input
    if not inc:
        return [CompletionItem(it["id"], help=it["help"]) for it in items[:10]]

    # 2) Fuzzy fallback: search in combined text
    if len(inc) >= 2:
        candidates = []
        item_map = {}
        for it in items:
            # Build searchable text from all fields
            searchable = f"{it['id']} {it['title']} {' and '.join(it['authors'])}"
            candidates.append((searchable, False))  # (text, is_archived)
            item_map[searchable] = it

        fuzzy_results = fuzzy_match(inc, candidates, limit=10, score_cutoff=40)
        completions = []
        for searchable, _, score in fuzzy_results:
            it = item_map.get(searchable)
            if it:
                completions.append(CompletionItem(it["id"], help=f"{it['help']} (fuzzy {score}%)"))
        return completions

    return []


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

    archive_dir = notes_dir / "archive"

    # Check if -a/--archived flag is set
    include_archived = ctx.params.get("archived", False)

    # Check if incomplete starts with "archive/"
    is_archive_path = incomplete.startswith("archive/")
    search_stem = incomplete[8:] if is_archive_path else incomplete

    # Collect file stems
    file_stems = []
    archived_stems = []

    if not is_archive_path:
        for path in notes_dir.glob("*.md"):
            if path.stem not in ("root", "backlog") and not path.name.startswith("."):
                file_stems.append(path.stem)

    if (include_archived or is_archive_path) and archive_dir.exists():
        for path in archive_dir.glob("*.md"):
            archived_stems.append(path.stem)

    # Use consolidated completion logic
    from .search import fuzzy_match

    return complete_files_with_fuzzy(
        search_stem=search_stem,
        file_stems=file_stems,
        archived_stems=archived_stems,
        fuzzy_match_fn=fuzzy_match,
        is_archive_path=is_archive_path,
        include_archived=include_archived
    )


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
    from .core.notes import parse_metadata
    from .search import fuzzy_match

    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []

    tasks = []

    # Collect all task file stems (metadata only - faster)
    for path in notes_dir.glob("*.md"):
        if path.stem in ("root", "backlog"):
            continue
        note = parse_metadata(path)
        if note and note.note_type == "task":
            tasks.append(path.stem)

    # Use consolidated completion logic
    return complete_filtered_with_fuzzy(
        search_stem=incomplete,
        items=tasks,
        fuzzy_match_fn=fuzzy_match
    )


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
