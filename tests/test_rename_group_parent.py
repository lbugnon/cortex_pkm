"""Test moving groups between projects."""

import pytest

from cor.maintenance import MaintenanceRunner


@pytest.fixture
def vault_with_groups(tmp_path):
    """Create a vault with projects and groups."""
    notes = tmp_path / "notes"
    notes.mkdir()
    
    # Project 1 with a group
    p1 = notes / "p1.md"
    p1.write_text("""---
type: project
status: active
---

# Project 1

## Tasks

- [ ] [Experiments](p1.experiments)
""")
    
    # Group under p1
    group = notes / "p1.experiments.md"
    group.write_text("""---
type: task
status: todo
parent: p1
---

# Experiments

[< Project 1](p1)

## Tasks

- [ ] [Task A](p1.experiments.task_a)
""")
    
    # Task under the group
    task = notes / "p1.experiments.task_a.md"
    task.write_text("""---
type: task
status: todo
parent: p1.experiments
---

# Task A

[< Experiments](p1.experiments)

## Description
""")
    
    # Project 2 (empty)
    p2 = notes / "p2.md"
    p2.write_text("""---
type: project
status: active
---

# Project 2

## Tasks
""")
    
    return {
        "vault": notes,
        "p1": p1,
        "p2": p2,
        "group": group,
        "task": task
    }


def test_move_group_to_different_project(vault_with_groups):
    """Moving a group to a different project should update both parent links."""
    notes = vault_with_groups["vault"]
    group = vault_with_groups["group"]
    
    # Simulate git rename: physically rename the file first
    new_group_path = notes / "p2.experiments.md"
    group.rename(new_group_path)
    
    runner = MaintenanceRunner(notes, dry_run=False)
    
    # Handle the rename
    updated, errors = runner.handle_renamed_files([("p1.experiments.md", "p2.experiments.md")])
    
    assert len(errors) == 0, f"Should not have errors: {errors}"
    
    # Check old parent (p1) no longer has the link
    p1_content = vault_with_groups["p1"].read_text()
    assert "experiments" not in p1_content.lower(), "p1 should not have experiments link anymore"
    
    # Check new parent (p2) has the link
    p2_content = vault_with_groups["p2"].read_text()
    assert "experiments" in p2_content.lower(), "p2 should have experiments link"
    assert "[Experiments](p2.experiments)" in p2_content or "experiments" in p2_content
    
    # Check group file updated
    group_content = new_group_path.read_text()
    assert "parent: p2" in group_content, "Group parent field should be updated to p2"
    assert "[< Project 2](p2)" in group_content, "Group backlink should point to p2"
    
    # Check child task's parent link updated (should now point to p2.experiments)
    task_content = vault_with_groups["task"].read_text()
    assert "parent: p2.experiments" in task_content, "Task parent should be updated to p2.experiments"


def test_move_group_with_tasks_updates_task_parents(vault_with_groups):
    """Moving a group should update parent references in child tasks."""
    notes = vault_with_groups["vault"]
    group = vault_with_groups["group"]
    task = vault_with_groups["task"]
    
    # Rename task first to match new parent
    new_task_path = notes / "p2.experiments.task_a.md"
    task.rename(new_task_path)
    
    # Then rename the group
    new_group_path = notes / "p2.experiments.md"
    group.rename(new_group_path)
    
    runner = MaintenanceRunner(notes, dry_run=False)
    
    # Handle both renames
    updated, errors = runner.handle_renamed_files([
        ("p1.experiments.md", "p2.experiments.md"),
        ("p1.experiments.task_a.md", "p2.experiments.task_a.md")
    ])
    
    assert len(errors) == 0, f"Should not have errors: {errors}"
    
    # Check p2 has the group link
    p2_content = vault_with_groups["p2"].read_text()
    assert "experiments" in p2_content.lower()
    
    # Check group has the task link
    group_content = new_group_path.read_text()
    assert "task_a" in group_content.lower()
    assert "parent: p2" in group_content
    
    # Check task updated
    task_content = new_task_path.read_text()
    assert "parent: p2.experiments" in task_content


def test_move_group_to_nonexistent_project(vault_with_groups):
    """Moving group to nonexistent project should fail."""
    notes = vault_with_groups["vault"]
    group = vault_with_groups["group"]
    
    # Simulate rename to nonexistent project
    new_group_path = notes / "nonexistent.experiments.md"
    group.rename(new_group_path)
    
    runner = MaintenanceRunner(notes, dry_run=False)
    
    updated, errors = runner.handle_renamed_files([("p1.experiments.md", "nonexistent.experiments.md")])
    
    assert len(errors) == 1
    assert "nonexistent" in errors[0]
    assert "does not exist" in errors[0]
