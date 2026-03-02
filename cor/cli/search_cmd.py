"""Search commands for Cortex CLI."""

import click

from . import cli
from cor.search import search_content, parse_search_query, filter_matches, SearchMatch
from ..utils import require_init, get_notes_dir


def _format_match(match: SearchMatch, query: str, show_context: bool = True) -> str:
    """Format a search match for display.

    Args:
        match: SearchMatch object
        query: Original search query (for highlighting)
        show_context: Whether to include context lines

    Returns:
        Formatted string for display
    """
    # Determine if archived
    is_archived = "archive" in match.file.parts
    archive_marker = " [archived]" if is_archived else ""

    # File name (relative to vault)
    notes_dir = get_notes_dir()
    try:
        rel_path = match.file.relative_to(notes_dir)
        file_display = str(rel_path)
    except ValueError:
        file_display = match.file.name

    # Highlight matching text
    content = match.content
    # Simple case-insensitive highlight
    lower_query = query.lower()
    lower_content = content.lower()
    if lower_query in lower_content and query:
        start = lower_content.index(lower_query)
        end = start + len(query)
        highlighted = (
            content[:start]
            + click.style(content[start:end], fg="green", bold=True)
            + content[end:]
        )
    else:
        highlighted = content

    lines = []

    # Header: file:line
    lines.append(
        click.style(f"{file_display}:{match.line}", fg="cyan", bold=True)
        + click.style(archive_marker, fg="yellow")
    )

    if show_context:
        # Context before
        for ctx_line in match.context_before:
            lines.append(f"  {click.style('|', fg='bright_black')} {ctx_line}")

        # Match line
        lines.append(f"  {click.style('|', fg='bright_black')} {highlighted}")

        # Context after
        for ctx_line in match.context_after:
            lines.append(f"  {click.style('|', fg='bright_black')} {ctx_line}")

        lines.append("")  # Empty line between results

    return "\n".join(lines)


@cli.command()
@click.option("--archived", "-a", is_flag=True, help="Include archived files in search")
@click.option("--limit", "-n", type=int, default=20, help="Maximum number of results")
@click.option("--no-context", is_flag=True, help="Hide context lines (compact output)")
@click.argument("query")
@require_init
def search(archived: bool, limit: int, no_context: bool, query: str):
    """Search content across all notes.

    Full-text search using ripgrep. Supports filters:

    \b
    Filters:
      status:VALUE     Filter by status (e.g., status:active)
      #TAG             Filter by tag (e.g., #urgent)
      project:NAME     Filter by project (e.g., project:foundation_model)

    \b
    Examples:
      cor search "neural network"              # Simple text search
      cor search "status:active ML"            # With filters
      cor search "#urgent"                     # Tag search
      cor search "neural status:active"        # Combined
      cor search "neural" -a -n 50             # Include archived, 50 results
      cor search "TODO" --no-context           # Compact output
    """
    # Parse query for filters
    text_query, filters = parse_search_query(query)

    if not text_query and not filters:
        click.echo("Error: Empty query. Provide search text or filters.", err=True)
        return

    # Show what we're searching for
    if text_query and filters:
        filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
        click.echo(f"Searching for '{click.style(text_query, bold=True)}' with filters: {filter_str}")
    elif filters:
        filter_str = ", ".join(f"{k}={v}" for k, v in filters.items())
        click.echo(f"Searching with filters: {filter_str}")
    else:
        click.echo(f"Searching for '{click.style(text_query, bold=True)}'")
    click.echo()

    # Search content
    try:
        matches = search_content(
            query=text_query,
            include_archived=archived,
            limit=limit,
            context_lines=2 if not no_context else 0,
        )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return

    if not matches:
        click.echo("No matches found.")
        return

    # Apply metadata filters
    if filters:
        matches = filter_matches(matches, filters)

    if not matches:
        click.echo("No matches found after applying filters.")
        return

    # Limit results
    matches = matches[:limit]

    # Display results
    show_context = not no_context
    for match in matches:
        click.echo(_format_match(match, text_query, show_context))

    # Summary
    total_str = f"{len(matches)} result" + ("s" if len(matches) != 1 else "")
    click.echo(click.style("-" * 40, fg="bright_black"))
    click.echo(f"{total_str}")
