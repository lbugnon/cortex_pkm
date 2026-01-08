"""Dependency tracking and resolution for tasks and projects."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .parser import Note


@dataclass
class DependencyInfo:
    """Information about a note's dependencies."""

    note_stem: str
    note_type: str  # "task", "project", etc.
    requires: list[str]  # Items this note requires
    blocked_by: list[str]  # Requirements that are unmet
    blocks: list[str]  # Items that require this note
    all_requirements_met: bool
    missing_requirements: list[str]  # Requirements that don't exist
    circular_dependencies: list[str]  # Circular dependency chain if detected


def calculate_inverse_dependencies(notes: list[Note]) -> dict[str, list[str]]:
    """Calculate inverse dependency mapping (note -> notes that require it).

    Args:
        notes: List of all notes

    Returns:
        Dict mapping note stem to list of note stems that require it
    """
    inverse = {}

    for note in notes:
        # Both tasks and projects can have dependencies
        if note.note_type not in ("task", "project"):
            continue

        note_stem = note.path.stem

        for requirement in note.requires:
            if requirement not in inverse:
                inverse[requirement] = []
            inverse[requirement].append(note_stem)

    return inverse


def check_dependencies_met(note: Note, all_notes: list[Note]) -> tuple[bool, list[str]]:
    """Check if all requirements for a note are met.

    Args:
        note: Note to check
        all_notes: All notes for looking up requirement status

    Returns:
        (all_met, unmet_requirements)
        - all_met: True if all requirements are done
        - unmet_requirements: List of requirement stems that are not done
    """
    if not note.requires:
        return True, []

    # Build lookup map
    notes_by_stem = {n.path.stem: n for n in all_notes}

    unmet = []
    for req_stem in note.requires:
        req_note = notes_by_stem.get(req_stem)
        if not req_note:
            # Requirement doesn't exist (will be caught in validation)
            continue

        # Check if requirement is complete
        # For tasks: done or dropped
        # For projects: done
        if req_note.note_type == "task":
            if req_note.status not in ("done", "dropped"):
                unmet.append(req_stem)
        elif req_note.note_type == "project":
            if req_note.status != "done":
                unmet.append(req_stem)

    return len(unmet) == 0, unmet


def detect_circular_dependencies(note_stem: str, all_notes: list[Note]) -> Optional[list[str]]:
    """Detect if note is part of a circular dependency chain.

    Args:
        note_stem: Note to check
        all_notes: All notes

    Returns:
        List representing the circular chain if found, None otherwise
        Example: ["a", "b", "c", "a"] means a->b->c->a
    """
    notes_by_stem = {n.path.stem: n for n in all_notes}

    def dfs(current: str, path: list[str], visited: set[str]) -> Optional[list[str]]:
        if current in path:
            # Found cycle
            cycle_start = path.index(current)
            return path[cycle_start:] + [current]

        if current in visited:
            return None

        visited.add(current)
        note = notes_by_stem.get(current)

        if not note or not note.requires:
            return None

        for req in note.requires:
            result = dfs(req, path + [current], visited)
            if result:
                return result

        return None

    return dfs(note_stem, [], set())


def validate_dependencies(note: Note, all_notes: list[Note]) -> list[str]:
    """Validate note dependencies.

    Args:
        note: Note to validate
        all_notes: All notes

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if not note.requires:
        return errors

    notes_by_stem = {n.path.stem: n for n in all_notes}

    # Check 1: All requirements exist
    for req_stem in note.requires:
        if req_stem not in notes_by_stem:
            errors.append(f"Requirement does not exist: {req_stem}")

    # Check 2: No self-dependency
    note_stem = note.path.stem
    if note_stem in note.requires:
        errors.append(f"Note cannot require itself")

    # Check 3: No circular dependencies
    circular = detect_circular_dependencies(note_stem, all_notes)
    if circular:
        cycle_str = " -> ".join(circular)
        errors.append(f"Circular dependency detected: {cycle_str}")

    return errors


def get_dependency_info(note: Note, all_notes: list[Note]) -> DependencyInfo:
    """Get comprehensive dependency information for a note.

    Args:
        note: Note to analyze
        all_notes: All notes

    Returns:
        DependencyInfo with all dependency details
    """
    note_stem = note.path.stem

    # Get items this note requires
    requires = note.requires if note.requires else []

    # Calculate inverse dependencies
    inverse_map = calculate_inverse_dependencies(all_notes)
    blocks = inverse_map.get(note_stem, [])

    # Check which requirements are met
    all_met, unmet = check_dependencies_met(note, all_notes)

    # Find missing requirements
    notes_by_stem = {n.path.stem: n for n in all_notes}
    missing = [req for req in requires if req not in notes_by_stem]

    # Detect circular dependencies
    circular = detect_circular_dependencies(note_stem, all_notes) or []

    return DependencyInfo(
        note_stem=note_stem,
        note_type=note.note_type,
        requires=requires,
        blocked_by=unmet,
        blocks=blocks,
        all_requirements_met=all_met,
        missing_requirements=missing,
        circular_dependencies=circular,
    )
