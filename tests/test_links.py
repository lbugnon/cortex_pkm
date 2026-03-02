"""Tests for cor/core/links.py module."""

import pytest
from pathlib import Path

from cor.core.links import Link, LinkPatterns, LinkManager


class TestLinkPatterns:
    """Test regex patterns."""

    def test_basic_link_pattern(self):
        """Test basic link pattern matches."""
        text = "[Title](target)"
        matches = list(LinkPatterns.LINK.finditer(text))

        assert len(matches) == 1
        assert matches[0].group(1) == "Title"
        assert matches[0].group(2) == "target"

    def test_archive_link_pattern(self):
        """Test archive link pattern."""
        text = "[Title](archive/file)"
        matches = list(LinkPatterns.ARCHIVE_LINK.finditer(text))

        assert len(matches) == 1
        assert matches[0].group(2) == "file"

    def test_task_entry_pattern(self):
        """Test task entry pattern matches."""
        text = "- [x] [Task Title](task.name)"
        matches = list(LinkPatterns.TASK_ENTRY.finditer(text))

        assert len(matches) == 1
        assert matches[0].group(2) == "x"  # checkbox
        assert matches[0].group(3) == "task.name"  # target

    def test_external_link_detection(self):
        """Test external link prefix detection via LinkPatterns."""
        mgr = LinkManager.__new__(LinkManager)
        mgr.notes_dir = None
        mgr.archive_dir = None
        assert mgr.is_external("https://example.com")
        assert mgr.is_external("http://example.com")
        assert mgr.is_external("mailto:test@example.com")
        assert mgr.is_external("#section")

        assert not mgr.is_external("internal.md")
        assert not mgr.is_external("archive/file.md")


class TestLinkManager:
    """Test LinkManager functionality."""

    @pytest.fixture
    def notes_dir(self, tmp_path):
        """Create a temporary notes directory."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "archive").mkdir()
        return notes_dir

    @pytest.fixture
    def link_mgr(self, notes_dir):
        """Create a LinkManager instance."""
        return LinkManager(notes_dir)

    def test_extract_links(self, link_mgr):
        """Test extracting links from content."""
        content = """
        [Task 1](task1.md)
        [Task 2](archive/task2.md)
        [External](https://example.com)
        [Parent](../parent.md)
        """

        links = link_mgr.extract_links(content)

        assert len(links) == 4
        assert links[0].target == "task1.md"
        assert not links[0].is_external
        assert not links[0].is_archive

        assert links[1].target == "archive/task2.md"
        assert links[1].is_archive

        assert links[2].target == "https://example.com"
        assert links[2].is_external

        assert links[3].target == "../parent.md"
        assert links[3].has_parent_prefix

    def test_update_archive_links_to_archive(self, link_mgr):
        """Test adding archive/ prefix to links."""
        content = "[Task](task1.md)\n[External](https://example.com)"

        result = link_mgr.update_archive_links(content, to_archive=True)

        assert "[Task](archive/task1.md)" in result
        assert "[External](https://example.com)" in result  # External unchanged

    def test_update_archive_links_from_archive(self, link_mgr):
        """Test removing archive/ prefix from links."""
        content = "[Task](archive/task1.md)"

        result = link_mgr.update_archive_links(content, to_archive=False)

        assert "[Task](task1.md)" in result

    def test_update_parent_prefix_add(self, link_mgr):
        """Test adding ../ prefix to parent links."""
        content = "[Parent](parent.md)\n[External](https://example.com)"

        result = link_mgr.update_parent_prefix(content, add_prefix=True)

        assert "[Parent](../parent.md)" in result
        assert "[External](https://example.com)" in result  # External unchanged

    def test_update_parent_prefix_remove(self, link_mgr):
        """Test removing ../ prefix from links."""
        content = "[Parent](../parent.md)"

        result = link_mgr.update_parent_prefix(content, add_prefix=False)

        assert "[Parent](parent.md)" in result

    def test_update_link_targets(self, link_mgr):
        """Test updating link targets (targets include .md extension)."""
        content = """
        [Task](old_task.md)
        [Archived](archive/old_task.md)
        """

        result = link_mgr.update_link_targets(content, "old_task.md", "new_task.md")

        assert "[Task](new_task.md)" in result
        assert "[Archived](archive/new_task.md)" in result

    def test_update_backlink(self, link_mgr):
        """Test updating backlink."""
        content = "[< Old Parent](old_parent.md)"

        result = link_mgr.update_backlink(content, "old_parent", "new_parent", "New Parent")

        assert "[< New Parent](new_parent.md)" in result

    def test_remove_task_entry(self, link_mgr):
        """Test removing task entry from parent content."""
        content = """## Tasks
- [x] [Task 1](task1.md)
- [ ] [Task 2](task2.md)
"""

        result = link_mgr.remove_task_entry(content, "task1")

        assert "task1" not in result
        assert "task2" in result

    def test_update_task_checkbox(self, link_mgr):
        """Test updating task checkbox symbol."""
        content = "- [ ] [Task](task1.md)"

        result = link_mgr.update_task_checkbox(content, "task1", "x")

        assert "- [x] [Task](task1.md)" in result

    def test_extract_task_entries(self, link_mgr):
        """Test extracting task entries."""
        content = """- [x] [Task 1](task1.md)
- [ ] [Task 2](archive/task2.md)
- [o] [Task 3](task3.md)
"""

        entries = link_mgr.extract_task_entries(content)

        assert len(entries) == 3
        assert entries[0][0] == "x"  # checkbox
        assert entries[0][2] == "task1.md"  # target (includes .md)
        assert entries[1][0] == " "
        assert entries[1][2] == "task2.md"  # Pattern captures stem without archive/ prefix

    def test_add_archive_prefix_to_children(self, link_mgr):
        """Test adding archive/ prefix to specific children."""
        content = """
        [Child 1](child1.md)
        [Child 2](child2.md)
        [Child 3](archive/child3.md)
        """

        result = link_mgr.add_archive_prefix_to_children(content, ["child1", "child2"])

        assert "[Child 1](archive/child1.md)" in result
        assert "[Child 2](archive/child2.md)" in result
        assert "[Child 3](archive/child3.md)" in result  # Already has prefix
