"""Tests for cor/core/archive.py module."""

import pytest
from pathlib import Path

from cor.core.archive import ArchiveManager, is_in_archive


class TestArchiveManager:
    """Test ArchiveManager functionality."""

    @pytest.fixture
    def notes_dir(self, tmp_path):
        """Create a temporary notes directory."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        return notes_dir

    @pytest.fixture
    def archive_mgr(self, notes_dir):
        """Create an ArchiveManager instance."""
        return ArchiveManager(notes_dir)

    def test_init_creates_archive_dir(self, notes_dir):
        """Test that initialization creates archive directory."""
        archive_mgr = ArchiveManager(notes_dir)

        assert archive_mgr.archive_dir.exists()
        assert archive_mgr.archive_dir == notes_dir / "archive"

    def test_is_in_archive_relative_path(self, archive_mgr):
        """Test archive detection with relative paths."""
        assert archive_mgr.is_in_archive("archive/file.md")
        assert archive_mgr.is_in_archive("archive\\file.md")  # Windows style

        assert not archive_mgr.is_in_archive("file.md")
        assert not archive_mgr.is_in_archive("other/file.md")

    def test_is_in_archive_absolute_path(self, archive_mgr, notes_dir):
        """Test archive detection with absolute paths."""
        archived_file = notes_dir / "archive" / "file.md"
        active_file = notes_dir / "file.md"

        # Create files
        archived_file.touch()
        active_file.touch()

        assert archive_mgr.is_in_archive(archived_file)
        assert not archive_mgr.is_in_archive(active_file)

    def test_get_archive_path(self, archive_mgr, notes_dir):
        """Test getting archive path for a stem."""
        path = archive_mgr.get_archive_path("task")

        assert path == notes_dir / "archive" / "task.md"

    def test_get_active_path(self, archive_mgr, notes_dir):
        """Test getting active path for a stem."""
        path = archive_mgr.get_active_path("task")

        assert path == notes_dir / "task.md"

    def test_archive_file(self, archive_mgr, notes_dir):
        """Test moving file to archive."""
        source = notes_dir / "task.md"
        source.write_text("content")

        result = archive_mgr.archive_file(source)

        assert result == notes_dir / "archive" / "task.md"
        assert not source.exists()
        assert result.exists()
        assert result.read_text() == "content"

    def test_unarchive_file(self, archive_mgr, notes_dir):
        """Test moving file from archive to active."""
        archive_dir = notes_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        source = archive_dir / "task.md"
        source.write_text("content")

        result = archive_mgr.unarchive_file(source)

        assert result == notes_dir / "task.md"
        assert not source.exists()
        assert result.exists()
        assert result.read_text() == "content"

    def test_should_archive_task(self, archive_mgr):
        """Test should_archive logic for tasks."""
        assert archive_mgr.should_archive("done", "task")
        assert archive_mgr.should_archive("dropped", "task")

        assert not archive_mgr.should_archive("todo", "task")
        assert not archive_mgr.should_archive("active", "task")
        assert not archive_mgr.should_archive("blocked", "task")

    def test_should_archive_project(self, archive_mgr):
        """Test should_archive logic for projects."""
        assert archive_mgr.should_archive("done", "project")

        assert not archive_mgr.should_archive("planning", "project")
        assert not archive_mgr.should_archive("active", "project")
        assert not archive_mgr.should_archive("paused", "project")

    def test_should_unarchive_task(self, archive_mgr):
        """Test should_unarchive logic for tasks."""
        assert archive_mgr.should_unarchive("todo", "task")
        assert archive_mgr.should_unarchive("active", "task")
        assert archive_mgr.should_unarchive("blocked", "task")

        assert not archive_mgr.should_unarchive("done", "task")
        assert not archive_mgr.should_unarchive("dropped", "task")

    def test_should_unarchive_project(self, archive_mgr):
        """Test should_unarchive logic for projects."""
        assert archive_mgr.should_unarchive("planning", "project")
        assert archive_mgr.should_unarchive("active", "project")
        assert archive_mgr.should_unarchive("paused", "project")

        assert not archive_mgr.should_unarchive("done", "project")

    def test_find_archived_file(self, archive_mgr, notes_dir):
        """Test finding archived file."""
        archive_dir = notes_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        archived = archive_dir / "task.md"
        archived.write_text("content")

        result = archive_mgr.find_archived_file("task")

        assert result == archived
        assert result.exists()

    def test_find_archived_file_not_found(self, archive_mgr):
        """Test finding non-existent archived file."""
        result = archive_mgr.find_archived_file("nonexistent")

        assert result is None

    def test_find_active_file(self, archive_mgr, notes_dir):
        """Test finding active file."""
        active = notes_dir / "task.md"
        active.write_text("content")

        result = archive_mgr.find_active_file("task")

        assert result == active
        assert result.exists()

    def test_find_file_in_active(self, archive_mgr, notes_dir):
        """Test finding file in active directory."""
        active = notes_dir / "task.md"
        active.write_text("content")

        result = archive_mgr.find_file("task")

        assert result is not None
        assert result[0] == active
        assert result[1] is False  # not archived

    def test_find_file_in_archive(self, archive_mgr, notes_dir):
        """Test finding file in archive directory."""
        archive_dir = notes_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        archived = archive_dir / "task.md"
        archived.write_text("content")

        result = archive_mgr.find_file("task")

        assert result is not None
        assert result[0] == archived
        assert result[1] is True  # archived

    def test_find_file_prefers_active(self, archive_mgr, notes_dir):
        """Test that find_file prefers active over archived."""
        active = notes_dir / "task.md"
        active.write_text("active content")

        archive_dir = notes_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        archived = archive_dir / "task.md"
        archived.write_text("archived content")

        result = archive_mgr.find_file("task")

        assert result is not None
        assert result[0] == active  # Prefers active
        assert result[1] is False


class TestConvenienceFunction:
    """Test convenience function."""

    def test_is_in_archive_convenience(self, tmp_path):
        """Test is_in_archive convenience function."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "archive").mkdir()

        archived_file = notes_dir / "archive" / "file.md"
        archived_file.touch()

        assert is_in_archive(archived_file, notes_dir)
        assert is_in_archive("archive/file.md", notes_dir)
