"""Consolidated shell completion logic for Cortex CLI.

This module extracts the common fuzzy fallback logic that was duplicated
in complete_existing_name() and complete_task_name().
"""

import os
from click.shell_completion import CompletionItem


def apply_fuzzy_completion_filter(
    fuzzy_results: list[tuple[str, bool, int]],
    collapse_exact: bool = None
) -> list[tuple[str, bool, int]]:
    """Apply standard filtering to fuzzy completion results.

    This extracts the common logic from complete_existing_name and complete_task_name:
    1. Keep results within 10 points of top score
    2. Optionally collapse 100% matches to single result

    Args:
        fuzzy_results: List of (stem, is_archived, score) tuples from fuzzy_match
        collapse_exact: If True, collapse 100% matches to one result.
                       If None, check COR_COMPLETE_COLLAPSE_100 environment variable.

    Returns:
        Filtered list of fuzzy results
    """
    if not fuzzy_results:
        return []

    # Filter: keep results within 10 points of top score
    # This helps the shell find a common prefix for autocomplete
    top_score = fuzzy_results[0][2]
    filtered = [r for r in fuzzy_results if r[2] >= top_score - 10]

    # Determine collapse behavior
    if collapse_exact is None:
        collapse_exact = os.environ.get("COR_COMPLETE_COLLAPSE_100", "0").lower() not in {
            "0", "false", "no"
        }

    # Collapse 100%-score ties to shortest
    if collapse_exact and top_score == 100:
        top_ties = [r for r in filtered if r[2] == top_score]
        if len(top_ties) > 1:
            # Return only the first one (fuzzy_match already sorts by length)
            return [filtered[0]]

    return filtered


def complete_with_fuzzy_fallback(
    search_stem: str,
    prefix_matches: list[CompletionItem],
    fuzzy_match_fn,
    candidates: list[tuple[str, bool]],
    min_chars: int = 2,
    limit: int = 5,
    score_cutoff: int = 50,
    collapse_exact: bool = None,
    format_archived: bool = True
) -> list[CompletionItem]:
    """Unified completion logic with prefix + fuzzy fallback.

    This consolidates the pattern:
    1. Try prefix matches first
    2. If no prefix matches and input is long enough, try fuzzy matching
    3. Apply standard filtering to fuzzy results
    4. Return CompletionItem objects

    Args:
        search_stem: Search string
        prefix_matches: Prefix-matched completions
        fuzzy_match_fn: Function to call for fuzzy matching
        candidates: List of (stem, is_archived) tuples for fuzzy matching
        min_chars: Minimum characters before fuzzy fallback
        limit: Maximum fuzzy results
        score_cutoff: Minimum fuzzy match score
        collapse_exact: Collapse 100% matches (None = check env var)
        format_archived: If True, format archived items as "archive/stem"

    Returns:
        List of CompletionItem objects
    """
    # Return prefix matches if found
    if prefix_matches:
        return prefix_matches

    # Require minimum characters for fuzzy matching
    if len(search_stem) < min_chars:
        return []

    # Try fuzzy matching
    fuzzy_results = fuzzy_match_fn(search_stem, candidates, limit=limit, score_cutoff=score_cutoff)

    # Apply standard filtering
    fuzzy_results = apply_fuzzy_completion_filter(fuzzy_results, collapse_exact)

    # Convert to CompletionItem objects
    completions = []
    for stem, is_archived, score in fuzzy_results:
        if is_archived and format_archived:
            completions.append(
                CompletionItem(f"archive/{stem}", help=f"(fuzzy {score}%)")
            )
        else:
            completions.append(
                CompletionItem(stem, help=f"(fuzzy {score}%)")
            )

    return completions


def complete_files_with_fuzzy(
    search_stem: str,
    file_stems: list[str],
    archived_stems: list[str],
    fuzzy_match_fn,
    is_archive_path: bool = False,
    include_archived: bool = False
) -> list[CompletionItem]:
    """Complete file names with prefix + fuzzy fallback.

    Handles the common pattern for completing note file names:
    - Try prefix matches in active and/or archived files
    - Fall back to fuzzy matching if no prefix matches

    Args:
        search_stem: Search string (without "archive/" prefix)
        file_stems: List of active file stems
        archived_stems: List of archived file stems
        fuzzy_match_fn: Fuzzy matching function
        is_archive_path: True if user typed "archive/"
        include_archived: True if archived files should be included

    Returns:
        List of CompletionItem objects
    """
    completions = []

    # Prefix matches from active files (unless user typed "archive/")
    if not is_archive_path:
        completions.extend([
            CompletionItem(stem)
            for stem in file_stems
            if not search_stem or stem.startswith(search_stem)
        ])

    # Prefix matches from archived files (if requested or user typed "archive/")
    if (include_archived or is_archive_path) and archived_stems:
        completions.extend([
            CompletionItem(f"archive/{stem}", help="(archived)")
            for stem in archived_stems
            if not search_stem or stem.startswith(search_stem)
        ])

    # If we have prefix matches or search is too short, return
    if completions or len(search_stem) < 2:
        return completions

    # Fuzzy fallback
    candidates = [(stem, False) for stem in file_stems]
    if include_archived or is_archive_path:
        candidates.extend([(stem, True) for stem in archived_stems])

    return complete_with_fuzzy_fallback(
        search_stem=search_stem,
        prefix_matches=[],  # Already tried prefix matching
        fuzzy_match_fn=fuzzy_match_fn,
        candidates=candidates,
        format_archived=True
    )


def complete_filtered_with_fuzzy(
    search_stem: str,
    items: list[str],
    fuzzy_match_fn,
    item_filter=None,
    help_text: str = ""
) -> list[CompletionItem]:
    """Complete from filtered list with fuzzy fallback.

    Simpler version for completing from a filtered/validated list
    (e.g., only tasks, only projects).

    Args:
        search_stem: Search string
        items: List of valid items
        fuzzy_match_fn: Fuzzy matching function
        item_filter: Optional function to filter items
        help_text: Help text template (can include {item})

    Returns:
        List of CompletionItem objects
    """
    # Apply filter if provided
    if item_filter:
        items = [item for item in items if item_filter(item)]

    # Prefix matches
    prefix_matches = []
    for item in items:
        if not search_stem or item.startswith(search_stem):
            help_str = help_text.format(item=item) if help_text else ""
            prefix_matches.append(CompletionItem(item, help=help_str))

    # Build candidates for fuzzy fallback (no archived flag for simple completion)
    candidates = [(item, False) for item in items]

    return complete_with_fuzzy_fallback(
        search_stem=search_stem,
        prefix_matches=prefix_matches,
        fuzzy_match_fn=fuzzy_match_fn,
        candidates=candidates,
        format_archived=False
    )
