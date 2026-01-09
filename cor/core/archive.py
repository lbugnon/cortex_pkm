"""Archive path detection and management for Cortex PKM.

This module consolidates archive path detection that was scattered across
multiple locations with inconsistent patterns.
"""

from pathlib import Path


class ArchiveManager:
    """Centralized archive operations."""

    def __init__(self, notes_dir: Path):
        """Initialize archive manager.

        Args:
            notes_dir: Path to notes directory
        """
        self.notes_dir = notes_dir
        self.archive_dir = notes_dir / "archive"

        # Ensure archive directory exists
        self.archive_dir.mkdir(exist_ok=True)

    def is_in_archive(self, filepath: str | Path) -> bool:
        """Check if file is in archive directory.

        Handles multiple path formats:
        - Relative: "archive/file.md"
        - Windows: "archive\\file.md"
        - Absolute: "/path/to/notes/archive/file.md"

        Args:
            filepath: Path to check (str or Path)

        Returns:
            True if file is in archive
        """
        filepath_str = str(filepath)
        path = Path(filepath) if isinstance(filepath, str) else filepath

        # Check relative path formats
        if filepath_str.startswith("archive/") or filepath_str.startswith("archive\\"):
            return True

        # Check if archive_dir appears in the string path
        if str(self.archive_dir) in filepath_str:
            return True

        # Check if absolute path has archive as parent
        if path.is_absolute() and self.archive_dir in path.parents:
            return True

        # Check if the file is directly in archive_dir
        if path.is_absolute() and path.parent == self.archive_dir:
            return True

        return False

    def get_archive_path(self, stem: str) -> Path:
        """Get path to archived file.

        Args:
            stem: File stem (without .md extension)

        Returns:
            Path to file in archive directory
        """
        return self.archive_dir / f"{stem}.md"

    def get_active_path(self, stem: str) -> Path:
        """Get path to active (non-archived) file.

        Args:
            stem: File stem (without .md extension)

        Returns:
            Path to file in notes directory
        """
        return self.notes_dir / f"{stem}.md"

    def archive_file(self, source: Path) -> Path:
        """Move file to archive.

        Args:
            source: Path to file to archive

        Returns:
            Path to archived file
        """
        dest = self.get_archive_path(source.stem)
        source.rename(dest)
        return dest

    def unarchive_file(self, source: Path) -> Path:
        """Move file from archive to active directory.

        Args:
            source: Path to archived file

        Returns:
            Path to unarchived file
        """
        dest = self.get_active_path(source.stem)
        source.rename(dest)
        return dest

    def should_archive(self, status: str, note_type: str) -> bool:
        """Determine if a note should be archived based on status.

        Args:
            status: Note status
            note_type: Note type (task, project, etc.)

        Returns:
            True if note should be archived
        """
        if note_type == "task":
            return status in ("done", "dropped")
        elif note_type == "project":
            return status == "done"
        return False

    def should_unarchive(self, status: str, note_type: str) -> bool:
        """Determine if an archived note should be unarchived.

        Args:
            status: Note status
            note_type: Note type (task, project, etc.)

        Returns:
            True if note should be unarchived
        """
        if note_type == "task":
            return status not in ("done", "dropped")
        elif note_type == "project":
            return status != "done"
        return False

    def find_archived_file(self, stem: str) -> Path | None:
        """Find archived file by stem.

        Args:
            stem: File stem to search for

        Returns:
            Path if found, None otherwise
        """
        archive_path = self.get_archive_path(stem)
        return archive_path if archive_path.exists() else None

    def find_active_file(self, stem: str) -> Path | None:
        """Find active file by stem.

        Args:
            stem: File stem to search for

        Returns:
            Path if found, None otherwise
        """
        active_path = self.get_active_path(stem)
        return active_path if active_path.exists() else None

    def find_file(self, stem: str) -> tuple[Path, bool] | None:
        """Find file in either active or archive directory.

        Args:
            stem: File stem to search for

        Returns:
            Tuple of (path, is_archived) if found, None otherwise
        """
        # Check active first
        active_path = self.find_active_file(stem)
        if active_path:
            return (active_path, False)

        # Check archive
        archive_path = self.find_archived_file(stem)
        if archive_path:
            return (archive_path, True)

        return None


def is_in_archive(filepath: str | Path, notes_dir: Path) -> bool:
    """Quick check if a file is in archive (convenience function).

    Args:
        filepath: Path to check
        notes_dir: Notes directory path

    Returns:
        True if file is in archive
    """
    archive_mgr = ArchiveManager(notes_dir)
    return archive_mgr.is_in_archive(filepath)
