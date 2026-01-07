"""Fuzzy search and interactive picker for Cortex CLI."""

import sys
from pathlib import Path
from typing import Optional

import click
from rapidfuzz import fuzz, process
from simple_term_menu import TerminalMenu

from .utils import get_notes_dir


def get_all_file_stems(include_archived: bool = False) -> list[tuple[str, bool]]:
    """Get all file stems with archive status.

    Returns list of (stem, is_archived) tuples.
    """
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []

    results = []

    # Main directory files
    for path in notes_dir.glob("*.md"):
        if path.stem not in ("root", "backlog"):
            results.append((path.stem, False))

    # Archived files
    if include_archived:
        archive_dir = notes_dir / "archive"
        if archive_dir.exists():
            for path in archive_dir.glob("*.md"):
                results.append((path.stem, True))

    return results


def fuzzy_match(
    query: str,
    candidates: list[tuple[str, bool]],
    limit: int = 10,
    score_cutoff: int = 50,
) -> list[tuple[str, bool, int]]:
    """Find fuzzy matches for query against candidates.

    Args:
        query: Search string
        candidates: List of (stem, is_archived) tuples
        limit: Maximum results to return
        score_cutoff: Minimum score (0-100) to include

    Returns:
        List of (stem, is_archived, score) sorted by score descending, then by length ascending
    """
    if not candidates:
        return []

    # Extract just stems for matching
    stems = [c[0] for c in candidates]

    # Use partial_ratio for good substring matching in filenames
    results = process.extract(
        query,
        stems,
        scorer=fuzz.partial_ratio,
        limit=limit,
        score_cutoff=score_cutoff,
    )

    # Map back to full tuples with scores
    stem_to_archived = {c[0]: c[1] for c in candidates}
    matches = [(match[0], stem_to_archived[match[0]], int(match[1])) for match in results]
    
    # Sort by score (descending), then by length (ascending) for ties
    # This ensures shorter matches are preferred when scores are equal
    matches.sort(key=lambda x: (-x[2], len(x[0])))
    
    return matches


def show_picker(
    matches: list[tuple[str, bool, int]], query: str
) -> Optional[tuple[str, bool]]:
    """Show interactive picker for fuzzy matches.

    Args:
        matches: List of (stem, is_archived, score) tuples
        query: Original query (for display)

    Returns:
        Selected (stem, is_archived) or None if cancelled
    """
    # Build menu options with scores
    options = []
    for stem, is_archived, score in matches:
        suffix = " (archived)" if is_archived else ""
        options.append(f"{stem}{suffix}  [{score}%]")

    # Add cancel option
    options.append("[Cancel]")

    click.echo(f"\nMultiple matches for '{query}':")

    menu = TerminalMenu(
        options,
        title="Select file (arrows to navigate, Enter to confirm, q to cancel):",
        menu_cursor_style=("fg_cyan", "bold"),
        menu_highlight_style=("bg_cyan", "fg_black"),
    )

    choice = menu.show()

    if choice is None or choice == len(options) - 1:
        # Cancelled or selected [Cancel]
        return None

    stem, is_archived, _ = matches[choice]
    return (stem, is_archived)


def resolve_file_fuzzy(
    name: str,
    include_archived: bool = False,
    auto_select_threshold: int = 95,
) -> Optional[tuple[str, bool]]:
    """Resolve a file name using fuzzy matching with interactive picker.

    Args:
        name: User-provided file name (possibly partial/fuzzy)
        include_archived: Whether to search archived files
        auto_select_threshold: Score above which to auto-select single match

    Returns:
        Tuple of (stem, is_archived) or None if cancelled/no match

    Raises:
        click.ClickException: If no matches found
    """
    notes_dir = get_notes_dir()

    # 1. Check for exact match first
    exact_path = notes_dir / f"{name}.md"
    if exact_path.exists():
        return (name, False)

    if include_archived:
        archive_path = notes_dir / "archive" / f"{name}.md"
        if archive_path.exists():
            return (name, True)

    # 2. Get candidates and run fuzzy search
    candidates = get_all_file_stems(include_archived)
    matches = fuzzy_match(name, candidates)

    if not matches:
        raise click.ClickException(f"No files found matching '{name}'")

    # 3. Single high-confidence match: auto-select
    if len(matches) == 1 and matches[0][2] >= auto_select_threshold:
        stem, is_archived, score = matches[0]
        click.echo(f"Auto-selected: {stem}" + (" (archived)" if is_archived else ""))
        return (stem, is_archived)

    # 4. Non-interactive mode: use best match with warning
    if not sys.stdin.isatty():
        if len(matches) > 1:
            click.echo(
                f"Warning: Multiple matches found, using best: {matches[0][0]}",
                err=True,
            )
        return (matches[0][0], matches[0][1])

    # 5. Multiple matches or low confidence: show picker
    return show_picker(matches, name)


def get_file_path(stem: str, is_archived: bool) -> Path:
    """Convert (stem, is_archived) to full file path."""
    notes_dir = get_notes_dir()
    if is_archived:
        return notes_dir / "archive" / f"{stem}.md"
    return notes_dir / f"{stem}.md"
