"""File refactoring commands for Cortex CLI (rename, group)."""

import re
import shutil

import click

from ..completions import complete_existing_name, complete_group_project, complete_project_tasks, complete_new_parent
from ..parser import parse_note
from ..utils import (
    get_notes_dir,
    get_template,
    render_template,
    format_title,
    add_task_to_project,
    require_init,
    log_info,
    log_verbose,
)


@click.command(short_help="Rename projects/tasks; supports parent shortcuts")
@click.option("--archived", "-a", is_flag=True, is_eager=True, help="Include archived files in search")
@click.argument("old_name", shell_complete=complete_existing_name)
@click.argument("new_name", shell_complete=complete_new_parent)
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@require_init
def rename(archived: bool, old_name: str, new_name: str, dry_run: bool):
    """Rename projects/tasks and update all related links.

    Supports fuzzy matching for old_name.

    \b
    Shortcuts for tasks (keeps the leaf name):
      cor rename p1.task1 p2           -> p2.task1
      cor rename p1.task1 p2.group     -> p2.group.task1
      cor rename p1.g1.task p2         -> p2.task

    \b
    Notes:
    - Creates the target group if it does not exist.
    - Updates parent/backlinks and all file references.
    - Use -a to include archived files.
    - Use --dry-run to preview changes.
    """
    from ..fuzzy import resolve_file_fuzzy, get_file_path

    notes_dir = get_notes_dir()
    archive_dir = notes_dir / "archive"

    # Handle "archive/" prefix if present (from tab completion)
    if old_name.startswith("archive/"):
        old_name = old_name[8:]
        archived = True

    # Use fuzzy matching to resolve old_name
    result = resolve_file_fuzzy(old_name, include_archived=archived)

    if result is None:
        return  # User cancelled

    old_name, in_archive = result
    main_file = get_file_path(old_name, in_archive)

    # Determine types and resolve shortcut behavior
    old_parts = old_name.split(".")
    new_parts = new_name.split(".")

    # Parse note to know if we're renaming a project or a task (group included)
    note = parse_note(main_file)

    # Project rename keeps validation: new_name must not contain dots
    if note.note_type == "project" and "." in new_name:
        raise click.ClickException(
            f"Invalid project name '{new_name}': dots are reserved for hierarchy. "
            "Use hyphens instead (e.g., 'v0-1' not 'v0.1')."
        )

    # Resolve shortcut for tasks: keep leaf name, change parent to project or project.group
    resolved_new_name = new_name
    if note.note_type == "task" and len(old_parts) >= 2:
        leaf = old_parts[-1]
        if len(new_parts) == 1:
            # cor rename p1.g1.task -> p2  => p2.task
            resolved_new_name = f"{new_parts[0]}.{leaf}"
        elif len(new_parts) == 2:
            # cor rename p1.task1 -> p2.group  => p2.group.task1
            resolved_new_name = f"{new_parts[0]}.{new_parts[1]}.{leaf}"
        else:
            # 3+ parts in new_name means explicit full rename; use as-is
            resolved_new_name = new_name


    # Collect all files to rename (main file + children)
    files_to_rename: list[tuple] = []
    target_dir = archive_dir if in_archive else notes_dir

    # Main file
    new_main_file = target_dir / f"{resolved_new_name}.md"
    if new_main_file.exists():
        raise click.ClickException(f"Target already exists: {new_main_file}")
    files_to_rename.append((main_file, new_main_file))

    # Find all children (files starting with old_name.)
    for search_dir in [notes_dir, archive_dir] if archive_dir.exists() else [notes_dir]:
        for child in search_dir.glob(f"{old_name}.*.md"):
            # Replace old prefix with new prefix
            child_suffix = child.stem[len(old_name):]  # e.g., ".task_name"
            new_child_name = f"{resolved_new_name}{child_suffix}.md"
            new_child_path = search_dir / new_child_name

            if new_child_path.exists():
                raise click.ClickException(f"Target already exists: {new_child_path}")
            files_to_rename.append((child, new_child_path))

    # Collect all files that need link updates
    files_to_update_links: list = []

    # All notes that might reference the renamed files
    for search_dir in [notes_dir, archive_dir] if archive_dir.exists() else [notes_dir]:
        for md_file in search_dir.glob("*.md"):
            files_to_update_links.append(md_file)

    # Preview mode
    if dry_run:
        log_info(click.style("\n=== Dry Run - No changes will be made ===\n", bold=True))

        log_verbose(click.style("Files to rename:", fg="cyan"))
        for old_path, new_path in files_to_rename:
            log_verbose(f"  {old_path} → {new_path}")

        log_verbose(click.style("\nLinks to update:", fg="cyan"))
        link_updates = []
        for file_path in files_to_update_links:
            content = file_path.read_text()
            updates = []

            for old_path, new_path in files_to_rename:
                old_stem = old_path.stem
                new_stem = new_path.stem

                # Check for links: [Title](filename) or [Title](archive/filename)
                patterns = [
                    (rf'\[([^\]]+)\]\({re.escape(old_stem)}\)', f'[\\1]({new_stem})'),
                    (rf'\[([^\]]+)\]\(archive/{re.escape(old_stem)}\)', f'[\\1](archive/{new_stem})'),
                ]

                for pattern, _ in patterns:
                    if re.search(pattern, content):
                        updates.append(f"{old_stem} → {new_stem}")

            if updates:
                link_updates.append((file_path, updates))

        for file_path, updates in link_updates:
            log_verbose(f"  {file_path}:")
            for update in set(updates):
                log_verbose(f"    - {update}")

        log_info(click.style("\nRun without --dry-run to apply changes.", fg="yellow"))
        return

    # Auto-create target group if needed (for task moves to project.group)
    if note.note_type == "task":
        resolved_parts = resolved_new_name.split(".")
        # Parent is project or project.group; create group if len>=3 and group missing
        if len(resolved_parts) >= 3:
            project = resolved_parts[0]
            group_name = resolved_parts[1]
            parent_group_stem = f"{project}.{group_name}"
            parent_group_path = (archive_dir if in_archive else notes_dir) / f"{parent_group_stem}.md"
            project_path = (archive_dir if in_archive else notes_dir) / f"{project}.md"
            if not project_path.exists():
                raise click.ClickException(f"Project not found: {project}.md")
            if not parent_group_path.exists():
                # Create group file from task template
                log_info(click.style("Creating target group:", fg="cyan"))
                project_note = parse_note(project_path)
                project_title = project_note.title if project_note else format_title(project)
                template = get_template("task")
                content = render_template(template, group_name, parent=project, parent_title=project_title)
                parent_group_path.write_text(content)
                # Add group to project's Tasks section
                add_task_to_project(project_path, group_name, parent_group_stem)
                log_info(f"  Created {parent_group_path}")

    # Perform renames
    log_info(click.style("Renaming files:", fg="cyan"))
    for old_path, new_path in files_to_rename:
        shutil.move(str(old_path), str(new_path))
        log_verbose(f"  {old_path} → {new_path}")

    # Handle parent changes and link updates using maintenance infrastructure
    from ..maintenance import MaintenanceRunner
    runner = MaintenanceRunner(notes_dir, dry_run=False)
    
    # Prepare list of renames for handle_renamed_files (relative paths)
    renamed_list = []
    for old_path, new_path in files_to_rename:
        # Convert to relative paths from notes_dir
        try:
            old_rel = old_path.relative_to(notes_dir)
        except ValueError:
            # File is in archive
            old_rel = old_path.relative_to(notes_dir.parent)
        
        try:
            new_rel = new_path.relative_to(notes_dir)
        except ValueError:
            # File is in archive
            new_rel = new_path.relative_to(notes_dir.parent)
        
        renamed_list.append((str(old_rel), str(new_rel)))
    
    if renamed_list:
        log_info(click.style("\nHandling parent changes and link updates:", fg="cyan"))
        updated, errors = runner.handle_renamed_files(renamed_list)
        
        if errors:
            for error in errors:
                log_info(click.style(f"  Warning: {error}", fg="yellow"))
        
        if updated:
            for file_path in updated:
                log_verbose(f"  Updated: {file_path}")

    # Update links in all files
    log_info(click.style("\nUpdating additional links:", fg="cyan"))
    for file_path in files_to_update_links:
        # Re-check if file exists (might have been renamed)
        if not file_path.exists():
            # Find the new path if this file was renamed
            for old_path, new_path in files_to_rename:
                if old_path == file_path:
                    file_path = new_path
                    break

        if not file_path.exists():
            continue

        content = file_path.read_text()
        original_content = content
        updates = []

        for old_path, new_path in files_to_rename:
            old_stem = old_path.stem
            new_stem = new_path.stem
            
            # Get base name for title formatting (last part after dot)
            old_parts = old_stem.split(".")
            new_parts = new_stem.split(".")
            new_base = new_parts[-1] if new_parts else new_stem
            new_title = format_title(new_base)

            # Update backlinks with title: [< Old Title](old) → [< New Title](new)
            # Match flexible whitespace: [< ... ](old_stem) where ... is any text
            backlink_pattern = rf'\[<\s+[^\]]*\]\({re.escape(old_stem)}\)'
            if re.search(backlink_pattern, content):
                content = re.sub(backlink_pattern, rf'[< {new_title}]({new_stem})', content)
                updates.append(f"[< ...] → [< {new_title}]")

            # Update archive backlinks: [< Old Title](../old) → [< New Title](../new)
            archive_backlink_pattern = rf'\[<\s+[^\]]*\]\(../{re.escape(old_stem)}\)'
            if re.search(archive_backlink_pattern, content):
                content = re.sub(archive_backlink_pattern, rf'[< {new_title}](../{new_stem})', content)
                updates.append(f"[< ...] (archive) → [< {new_title}] (archive)")

            # Update regular links: [Title](filename) → [Title](new_filename)
            # But skip backlinks (those starting with <)
            pattern = rf'\[(?<!<\s)([^\]]+)\]\({re.escape(old_stem)}\)'
            if re.search(pattern, content):
                content = re.sub(pattern, rf'[\1]({new_stem})', content)
                updates.append(f"({old_stem}) → ({new_stem})")

            # Update archive links: [Title](archive/filename) → [Title](archive/new_filename)
            # But skip backlinks
            pattern = rf'\[(?<!<\s)([^\]]+)\]\(archive/{re.escape(old_stem)}\)'
            if re.search(pattern, content):
                content = re.sub(pattern, rf'[\1](archive/{new_stem})', content)
                updates.append(f"(archive/{old_stem}) → (archive/{new_stem})")

        if content != original_content:
            file_path.write_text(content)
            log_info(f"  {file_path}: {', '.join(set(updates))}")

    # Update reverse links in renamed files (the [< Parent](parent) links)
    log_info(click.style("\nUpdating reverse links:", fg="cyan"))
    for old_path, new_path in files_to_rename:
        if not new_path.exists():
            continue

        content = new_path.read_text()
        original_content = content

        # Get the new parent name from the new filename
        new_parts = new_path.stem.split(".")
        if len(new_parts) >= 2:
            new_parent = ".".join(new_parts[:-1])
            old_parts = old_path.stem.split(".")
            old_parent = ".".join(old_parts[:-1]) if len(old_parts) >= 2 else None

            if old_parent and old_parent != new_parent:
                # Get the base name of the new parent for title formatting
                parent_parts = new_parent.split(".")
                parent_base_name = parent_parts[-1] if len(parent_parts) > 0 else new_parent
                new_parent_title = format_title(parent_base_name)
                
                # Update parent frontmatter
                content = re.sub(
                    rf'^(parent:\s*){re.escape(old_parent)}$',
                    rf'\1{new_parent}',
                    content,
                    flags=re.MULTILINE,
                )

                # Update reverse link with proper title format
                # Match any link text to the old parent and replace with new parent link and title
                pattern = rf'\[([^\]]*)\]\({re.escape(old_parent)}\)'
                if re.search(pattern, content):
                    content = re.sub(pattern, rf'[< {new_parent_title}]({new_parent})', content)

                pattern = rf'\[([^\]]*)\]\(archive/{re.escape(old_parent)}\)'
                if re.search(pattern, content):
                    content = re.sub(pattern, rf'[< {new_parent_title}](archive/{new_parent})', content)

        if content != original_content:
            new_path.write_text(content)
            log_info(f"  Updated parent link in {new_path}")

    # Update titles in renamed files
    log_info(click.style("\nUpdating titles:", fg="cyan"))
    for old_path, new_path in files_to_rename:
        if not new_path.exists():
            continue

        # Determine if this is a project (no dots in stem)
        is_project = "." not in new_path.stem
        
        # Get the base name for title formatting
        if is_project:
            # For project, use the full name
            base_name = new_path.stem
        else:
            # For tasks/groups, use the last part
            parts = new_path.stem.split(".")
            base_name = parts[-1]
        
        # Format the new title
        new_title = format_title(base_name)
        
        # Update the title in the file
        content = new_path.read_text()
        original_content = content
        
        # Try to update the H1 heading (# Title)
        lines = content.split('\n')
        updated = False
        
        for i, line in enumerate(lines):
            # Look for the first H1 heading (outside frontmatter)
            if line.startswith('# ') and i > 0:  # Skip if it's in frontmatter area
                # Check if we're past frontmatter
                in_frontmatter = False
                for j in range(i):
                    if lines[j].strip() == '---':
                        in_frontmatter = not in_frontmatter
                
                if not in_frontmatter:
                    old_title = line[2:].strip()
                    lines[i] = f"# {new_title}"
                    updated = True
                    log_info(f"  {new_path}: '{old_title}' → '{new_title}'")
                    break
        
        if updated:
            content = '\n'.join(lines)
            new_path.write_text(content)

    log_info(click.style("\nDone!", fg="green"))


@click.command(short_help="Create a group and move tasks under it")
@click.argument("group", shell_complete=complete_group_project)
@click.argument("tasks", nargs=-1, shell_complete=complete_project_tasks)
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them")
@require_init
def group(group: str, tasks: tuple, dry_run: bool):
    """Group existing tasks under a new or existing group.

    \b
    Examples:
      cor group myproj.refactor task1 task2
      cor group myproj.v2 feature1 feature2

    \b
    Notes:
    - Creates the group file if it does not exist.
    - Updates parent/backlinks and links accordingly.
    - Use --dry-run to preview changes.
    """
    notes_dir = get_notes_dir()

    # Parse group argument
    if "." not in group:
        raise click.ClickException(
            "Group must be in format 'project.groupname'. Example: cor group myproject.refactor task1 task2"
        )

    parts = group.split(".")
    if len(parts) != 2:
        raise click.ClickException(
            "Group must have exactly one dot: 'project.groupname'"
        )

    project, group_name = parts

    # Validate project exists
    project_path = notes_dir / f"{project}.md"
    if not project_path.exists():
        raise click.ClickException(f"Project not found: {project}.md")

    # Validate at least one task provided
    if not tasks:
        raise click.ClickException("At least one task must be specified")

    # Validate all tasks exist
    files_to_rename: list[tuple] = []
    for task in tasks:
        task_path = notes_dir / f"{project}.{task}.md"
        if not task_path.exists():
            raise click.ClickException(f"Task not found: {project}.{task}.md")

        new_task_path = notes_dir / f"{project}.{group_name}.{task}.md"
        if new_task_path.exists():
            raise click.ClickException(f"Target already exists: {new_task_path}")

        files_to_rename.append((task_path, new_task_path))

    # Check group file doesn't exist
    group_path = notes_dir / f"{group}.md"
    if group_path.exists():
        raise click.ClickException(f"Group already exists: {group}.md")

    # Collect all files that need link updates
    files_to_update_links: list = []
    archive_dir = notes_dir / "archive"
    for search_dir in [notes_dir, archive_dir] if archive_dir.exists() else [notes_dir]:
        for md_file in search_dir.glob("*.md"):
            files_to_update_links.append(md_file)

    # Preview mode
    if dry_run:
        log_info(click.style("\n=== Dry Run - No changes will be made ===\n", bold=True))

        log_info(click.style("Group to create:", fg="cyan"))
        log_info(f"  {group_path}")

        log_info(click.style("\nTasks to move:", fg="cyan"))
        for old_path, new_path in files_to_rename:
            log_info(f"  {old_path.name} → {new_path.name}")

        log_info(click.style("\nLinks to update:", fg="cyan"))
        for old_path, new_path in files_to_rename:
            old_stem = old_path.stem
            new_stem = new_path.stem
            log_info(f"  ({old_stem}) → ({new_stem})")  
        log_info(click.style("\nRun without --dry-run to apply changes.", fg="yellow"))
        return

    # Create group file from task template
    log_info(click.style("Creating group:", fg="cyan"))

    project_note = parse_note(project_path)
    project_title = project_note.title if project_note else format_title(project)

    template = get_template("task")
    content = render_template(template, group_name, parent=project, parent_title=project_title)
    group_path.write_text(content)
    log_info(f"  Created {group_path}")

    # Add group to project's Tasks section
    add_task_to_project(project_path, group_name, group)

    # Rename task files
    log_info(click.style("\nMoving tasks:", fg="cyan"))
    for old_path, new_path in files_to_rename:
        shutil.move(str(old_path), str(new_path))
        log_info(f"  {old_path.name} → {new_path.name}")

    # Update links in all files
    log_info(click.style("\nUpdating links:", fg="cyan"))
    for file_path in files_to_update_links:
        # Skip if file was renamed
        if not file_path.exists():
            for old_path, new_path in files_to_rename:
                if old_path == file_path:
                    file_path = new_path
                    break

        if not file_path.exists():
            continue

        content = file_path.read_text()
        original_content = content
        updates = []

        for old_path, new_path in files_to_rename:
            old_stem = old_path.stem
            new_stem = new_path.stem

            # Update links: [Title](filename) → [Title](new_filename)
            pattern = rf'\[([^\]]+)\]\({re.escape(old_stem)}\)'
            if re.search(pattern, content):
                content = re.sub(pattern, rf'[\1]({new_stem})', content)
                updates.append(f"({old_stem}) → ({new_stem})")

            # Update archive links
            pattern = rf'\[([^\]]+)\]\(archive/{re.escape(old_stem)}\)'
            if re.search(pattern, content):
                content = re.sub(pattern, rf'[\1](archive/{new_stem})', content)
                updates.append(f"(archive/{old_stem}) → (archive/{new_stem})")

        if content != original_content:
            file_path.write_text(content)
            log_info(f"  {file_path}: {', '.join(set(updates))}")

    # Update parent links in renamed files to point to group instead of project
    log_info(click.style("\nUpdating parent links:", fg="cyan"))

    group_note = parse_note(group_path)
    group_title = group_note.title if group_note else format_title(group_name)

    for old_path, new_path in files_to_rename:
        content = new_path.read_text()
        original_content = content

        # Update parent in frontmatter
        content = re.sub(
            rf'^parent: {re.escape(project)}$',
            f'parent: {group}',
            content,
            flags=re.MULTILINE
        )

        # Update reverse link: [< Project Title](project) → [< Group Title](group)
        content = re.sub(
            rf'\[< [^\]]+\]\({re.escape(project)}\)',
            f'[< {group_title}]({group})',
            content
        )

        if content != original_content:
            new_path.write_text(content)
            log_info(f"  Updated parent in {new_path.name}")

    # Add tasks to group's Tasks section
    log_info(click.style("\nAdding tasks to group:", fg="cyan"))
    for _, new_path in files_to_rename:
        task_name = new_path.stem.split(".")[-1]  # Get last part
        add_task_to_project(group_path, task_name, new_path.stem)
    log_info(f"  Added {len(files_to_rename)} task(s) to {group}.md")
    # Remove old task entries from project (they're now under the group)
    # Note: links were already updated to new paths, so we match on new_stem
    log_info(click.style("\nCleaning up project:", fg="cyan"))
    project_content = project_path.read_text()
    original_project_content = project_content

    for _, new_path in files_to_rename:
        new_stem = new_path.stem
        # Remove task entries (links already point to new paths after update step)
        project_content = re.sub(
            rf'^- \[[^\]]*\] \[[^\]]+\]\({re.escape(new_stem)}\)\n',
            '',
            project_content,
            flags=re.MULTILINE
        )

    if project_content != original_project_content:
        project_path.write_text(project_content)
        log_info(f"  Removed old task entries from {project}.md")

    log_info(click.style("\nDone! Changes are staged for commit.", fg="green"))