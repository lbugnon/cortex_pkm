"""Tests for Telegram inbox functionality."""

import pytest
from pathlib import Path
from datetime import datetime

# Tests would require mocking Telegram API, leaving as placeholder
# The actual implementation is tested through integration tests


def test_get_existing_inbox_items(temp_vault):
    """Test extracting existing inbox items from backlog."""
    from cor.commands.inbox import _get_existing_inbox_items
    
    backlog_path = temp_vault / "backlog.md"
    
    # Write test content
    content = """---
created: 2025-01-01
modified: 2025-01-01
---
# Backlog

Capture anything here.

## Inbox

- First item
- Second item
- Duplicate item

## Notes

- This should not be counted
- Another note
"""
    backlog_path.write_text(content)
    
    existing = _get_existing_inbox_items(backlog_path)
    
    assert "first item" in existing
    assert "second item" in existing
    assert "duplicate item" in existing
    assert "this should not be counted" not in existing


def test_get_existing_inbox_items_empty(temp_vault):
    """Test extracting items from empty backlog."""
    from cor.commands.inbox import _get_existing_inbox_items
    
    backlog_path = temp_vault / "backlog.md"
    backlog_path.write_text("""---
created: 2025-01-01
---
# Backlog

## Inbox

""")
    
    existing = _get_existing_inbox_items(backlog_path)
    assert len(existing) == 0


def test_get_existing_inbox_items_no_file():
    """Test extracting items when file doesn't exist."""
    from cor.commands.inbox import _get_existing_inbox_items
    
    existing = _get_existing_inbox_items(Path("/nonexistent/backlog.md"))
    assert len(existing) == 0
