"""Tests for TUI interactive tree browser."""

import pytest
from pathlib import Path


def test_tui_module_imports():
    """Test that TUI module can be imported."""
    from cor.tui.tree_app import ProjectTreeApp, TaskNode, STATUS_KEYS
    
    # Verify status keys are mapped correctly
    assert "x" in STATUS_KEYS
    assert STATUS_KEYS["x"][0] == "done"
    assert "o" in STATUS_KEYS
    assert STATUS_KEYS["o"][0] == "blocked"


def test_task_node_display():
    """Test TaskNode display formatting."""
    from cor.tui.tree_app import TaskNode
    from rich.text import Text
    
    node = TaskNode(
        stem="project.task",
        title="Test Task",
        status="active",
        note_type="task",
        file_path=Path("/tmp/test.md")
    )
    
    label = node.get_rich_label()
    assert isinstance(label, Text)
    assert "[.]" in str(label)
    assert "Test Task" in str(label)


def test_tree_command_has_interactive_flag():
    """Test that tree command accepts -i/--interactive flag."""
    from click.testing import CliRunner
    from cor.cli import cli
    
    runner = CliRunner()
    result = runner.invoke(cli, ['tree', '--help'])
    
    assert result.exit_code == 0
    assert '-i, --interactive' in result.output
    assert 'Interactive mode' in result.output
    assert 'j/k' in result.output  # vim keys documented
    assert 'x' in result.output  # done key documented


@pytest.mark.asyncio
async def test_tui_app_basic_functionality(temp_vault):
    """Test basic TUI app functionality with pilot."""
    from cor.tui.tree_app import ProjectTreeApp
    
    # Create a test project with tasks
    vault = temp_vault
    
    # Create project
    project_file = vault / "test-project.md"
    project_file.write_text("""---
type: project
status: active
created: 2026-01-01 00:00
---
# Test Project

Summary here.
""")
    
    # Create task
    task_file = vault / "test-project.task1.md"
    task_file.write_text("""---
type: task
status: todo
created: 2026-01-01 00:00
parent: test-project
---
# Task1

[< Test Project](test-project)

## Description

Test task description.
""")
    
    # Create app
    app = ProjectTreeApp("test-project", vault)
    
    # Use pilot to test the app
    async with app.run_test() as pilot:
        # Let it settle
        await pilot.pause()
        
        # Check that tree is populated
        tree = app.query_one("Tree")
        assert tree is not None
        
        # Check that root has children
        assert len(tree.root.children) > 0
        
        # Test navigation with 'j' key
        await pilot.press("j")
        await pilot.pause()
        
        # Test quit
        await pilot.press("q")
        await pilot.pause()


def test_status_change_updates_file(temp_vault):
    """Test that status change works via cor mark command integration."""
    from click.testing import CliRunner
    from cor.cli import cli
    import frontmatter
    
    vault = temp_vault
    
    # Create task
    task_file = vault / "project.task1.md"
    task_file.write_text("""---
type: task
status: todo
created: 2026-01-01 00:00
parent: project
---
# Task1
""")
    
    # Verify initial status
    post = frontmatter.load(task_file)
    assert post['status'] == 'todo'
    
    # Use cor mark command to change status (same as TUI does)
    runner = CliRunner()
    result = runner.invoke(cli, ['mark', 'project.task1', 'active'])
    
    # Verify command succeeded
    assert result.exit_code == 0, f"Command failed: {result.output}"
    
    # Verify status changed
    post = frontmatter.load(task_file)
    assert post['status'] == 'active'


