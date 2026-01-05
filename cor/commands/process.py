"""Interactive processing commands for Cortex CLI (process, refine)."""

import re

import click

from ..utils import (
    get_notes_dir,
    get_projects,
    get_template,
    render_template,
    format_title,
    add_task_to_project,
    require_init,
    log_info,
    log_verbose,
    log_debug,
)


@click.command()
@require_init
def process():
    """Interactive prompt to file backlog items into projects.

    Reads backlog.md, shows each item, and prompts to:
    - Move to a project as a task
    - Keep in backlog
    - Delete

    Items are processed one by one with keyboard shortcuts.
    """
    notes_dir = get_notes_dir()

    backlog_path = notes_dir / "backlog.md"
    if not backlog_path.exists():
        raise click.ClickException("No backlog.md found. Run 'cor init' first.")

    # Parse backlog items (lines starting with - in ## Inbox section)
    content = backlog_path.read_text()
    lines = content.split("\n")

    inbox_items = []
    in_inbox = False

    for i, line in enumerate(lines):
        if line.strip() == "## Inbox":
            in_inbox = True
            continue
        if in_inbox:
            # Stop at next section
            if line.startswith("## "):
                break
            # Capture non-empty list items
            if line.strip().startswith("- ") and len(line.strip()) > 2:
                item_text = line.strip()[2:].strip()
                if item_text:
                    inbox_items.append((i, item_text))

    if not inbox_items:
        log_info(click.style("Backlog is empty. Nothing to process!", fg="green"))
        return

    # Get available projects
    projects = get_projects()

    log_info(click.style(f"\nProcessing {len(inbox_items)} backlog items...\n", bold=True))
    log_verbose("Commands: [p]roject, [k]eep, [d]elete, [q]uit\n")

    items_to_remove = []  # Line indices to remove
    items_to_keep = []    # Items to keep

    for line_idx, item_text in inbox_items:
        click.echo(click.style(f"  → {item_text}", fg="cyan"))

        while True:
            choice = click.prompt(
                "  Action",
                type=click.Choice(["p", "k", "d", "q"]),
                show_choices=True,
                default="k"
            )

            if choice == "q":
                click.echo("\nQuitting. Keeping remaining items in backlog.")
                # Keep all unprocessed items
                remaining_indices = [idx for idx, _ in inbox_items if idx >= line_idx]
                for idx in remaining_indices:
                    if idx not in items_to_remove:
                        original_item = next((t for i, t in inbox_items if i == idx), None)
                        if original_item:
                            items_to_keep.append(original_item)
                break

            elif choice == "k":
                log_verbose(click.style("  Keeping in backlog.", dim=True))
                items_to_keep.append(item_text)
                items_to_remove.append(line_idx)
                break

            elif choice == "d":
                log_verbose(click.style("  Deleted.", fg="red", dim=True))
                items_to_remove.append(line_idx)
                break

            elif choice == "p":
                if not projects:
                    click.echo(click.style("  No projects found. Create one first.", fg="red"))
                    continue

                # Show numbered project list
                click.echo("\n  Available projects:")
                for i, proj in enumerate(projects, 1):
                    click.echo(f"    {i}. {proj}")

                proj_choice = click.prompt(
                    "  Select project (number or name)",
                    default="1"
                )

                # Parse choice
                selected_project = None
                try:
                    idx = int(proj_choice) - 1
                    if 0 <= idx < len(projects):
                        selected_project = projects[idx]
                except ValueError:
                    # Try matching by name
                    if proj_choice in projects:
                        selected_project = proj_choice
                    else:
                        # Partial match
                        matches = [p for p in projects if proj_choice.lower() in p.lower()]
                        if len(matches) == 1:
                            selected_project = matches[0]

                if not selected_project:
                    click.echo(click.style("  Invalid project. Try again.", fg="red"))
                    continue

                # Convert item to task name (sanitize)
                task_name = re.sub(r'[^a-zA-Z0-9_-]', '_', item_text.lower())
                task_name = re.sub(r'_+', '_', task_name).strip('_')[:50]

                task_name = click.prompt(
                    "  Task name",
                    default=task_name
                )

                # Create task file
                task_filename = f"{selected_project}.{task_name}"
                filepath = notes_dir / f"{task_filename}.md"

                if filepath.exists():
                    click.echo(click.style(f"  Task already exists: {filepath}", fg="red"))
                    continue

                # Read and render template
                template = get_template("task")
                task_content = render_template(
                    template, task_name, selected_project, format_title(selected_project)
                )

                # Add original item text to description
                task_content = task_content.replace(
                    "## Description\n",
                    f"## Description\n{item_text}\n"
                )

                filepath.write_text(task_content)
                log_info(click.style(f"  Created {filepath}", fg="green"))

                # Add task to project's Tasks section
                project_path = notes_dir / f"{selected_project}.md"
                add_task_to_project(project_path, task_name, task_filename)
                log_info(click.style(f"  Added to {project_path}", fg="green"))

                items_to_remove.append(line_idx)
                break

        if choice == "q":
            break

    # Rebuild backlog with remaining items
    new_lines = []
    for i, line in enumerate(lines):
        if i in items_to_remove:
            continue
        new_lines.append(line)

    # Find inbox section and add kept items back
    new_content = "\n".join(new_lines)

    # Ensure inbox section has kept items
    if items_to_keep:
        # Re-parse to find inbox section
        new_lines = new_content.split("\n")
        final_lines = []
        inbox_found = False

        for i, line in enumerate(new_lines):
            final_lines.append(line)
            if line.strip() == "## Inbox":
                inbox_found = True
                # Add kept items after section header
                for item in items_to_keep:
                    final_lines.append(f"- {item}")

        if not inbox_found:
            # Add inbox section at end
            final_lines.append("## Inbox")
            for item in items_to_keep:
                final_lines.append(f"- {item}")

        new_content = "\n".join(final_lines)

    # Ensure file ends properly
    if not new_content.endswith("\n"):
        new_content += "\n"

    backlog_path.write_text(new_content)
    log_info(click.style("\nBacklog updated.", fg="green"))


@click.command()
@click.argument("project", shell_complete=complete_project)
@click.option("--explain", "-e", is_flag=True, help="Show prompt and raw response for debugging")
@click.option("--model", "-m", default="qwen2.5:0.5b", help="Ollama model to use")
@require_init
def refine(project: str, explain: bool, model: str):
    """Get LLM suggestions to improve project goals.

    Uses local Ollama to analyze a project and suggest improvements.
    Requires Ollama running locally (ollama serve).

    Examples:
        cor refine my-project        # Analyze project
        cor refine my-project -e     # Show prompt/response for debugging
    """
    from ..llm import refine_project

    notes_dir = get_notes_dir()

    project_path = notes_dir / f"{project}.md"
    if not project_path.exists():
        raise click.ClickException(f"Project not found: {project}")

    content = project_path.read_text()
    note = parse_note(project_path)
    task_count = len(list(notes_dir.glob(f"{project_path.stem}.*.md")))

    click.echo(click.style(f"\n═══ {note.title} ═══", bold=True))

    prompt, response, error = refine_project(content, task_count, model)

    if explain:
        click.echo(click.style("\n[Prompt]", fg="cyan", dim=True))
        click.echo(prompt)
        click.echo()

    if error:
        click.echo(click.style(f"Error: {error}", fg="red"))
        return

    if explain:
        click.echo(click.style("[Response]", fg="cyan", dim=True))

    if response.strip():
        click.echo(response.strip())
    else:
        click.echo(click.style("No suggestions - looks good!", fg="green"))

    click.echo()
