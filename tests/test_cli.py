"""Tests for CLI commands.

Tests cover:
- cor init
- cor new (project, task, note)
- cor status
- cor projects
- cor tree
- cor rename
- cor group
"""

import pytest
from click.testing import CliRunner

from cor.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def initialized_vault(temp_vault, runner):
    """Return a vault that has been initialized with cor init."""
    # temp_vault already has templates and root.md from conftest
    return temp_vault


class TestInit:
    """Test cor init command."""

    def test_init_creates_root_md(self, runner, tmp_path, monkeypatch):
        """cor init should create root.md"""
        monkeypatch.chdir(tmp_path)

        # Initialize git first
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        result = runner.invoke(cli, ["init", "--yes"])
        assert result.exit_code == 0, f"Init failed: {result.output}"
        assert (tmp_path / "root.md").exists(), "root.md should be created"

    def test_init_creates_templates(self, runner, tmp_path, monkeypatch):
        """cor init should create template files."""
        monkeypatch.chdir(tmp_path)

        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

        result = runner.invoke(cli, ["init", "--yes"])
        assert result.exit_code == 0

        templates = tmp_path / "templates"
        assert templates.exists(), "templates/ directory should be created"
        assert (templates / "project.md").exists(), "project template should exist"
        assert (templates / "task.md").exists(), "task template should exist"
        assert (templates / "note.md").exists(), "note template should exist"


class TestNew:
    """Test cor new command."""

    def test_new_project_creates_file(self, runner, initialized_vault, monkeypatch):
        """cor new project should create a project file."""
        monkeypatch.chdir(initialized_vault)

        result = runner.invoke(cli, ["new", "project", "testproject", "--no_edit"])
        assert result.exit_code == 0, f"New project failed: {result.output}"
        assert (initialized_vault / "testproject.md").exists()

    def test_new_project_has_frontmatter(self, runner, initialized_vault, monkeypatch):
        """New project should have proper frontmatter."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "testproject", "--no_edit"])

        content = (initialized_vault / "testproject.md").read_text()
        assert "status: planning" in content, "Project should have planning status"
        assert "created:" in content, "Project should have created date"

    def test_new_task_under_project(self, runner, initialized_vault, monkeypatch):
        """cor new task project.taskname should create task under project."""
        monkeypatch.chdir(initialized_vault)

        # Create project first
        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])

        # Create task
        result = runner.invoke(cli, ["new", "task", "myproj.mytask", "--no_edit"])
        assert result.exit_code == 0, f"New task failed: {result.output}"
        assert (initialized_vault / "myproj.mytask.md").exists()

    def test_new_task_has_parent_link(self, runner, initialized_vault, monkeypatch):
        """New task should have link back to parent project."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.mytask", "--no_edit"])

        content = (initialized_vault / "myproj.mytask.md").read_text()
        assert "parent: myproj" in content, "Task should have parent field"
        assert "(myproj)" in content, "Task should have link to parent"

    def test_new_task_added_to_project(self, runner, initialized_vault, monkeypatch):
        """New task should be added to project's Tasks section."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.mytask", "--no_edit"])

        content = (initialized_vault / "myproj.md").read_text()
        assert "(myproj.mytask)" in content, "Project should link to task"
        assert "[ ]" in content, "Project should have todo checkbox for task"

    def test_new_task_creates_group_if_needed(self, runner, initialized_vault, monkeypatch):
        """cor new task project.group.task should create group if it doesn't exist."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        result = runner.invoke(cli, ["new", "task", "myproj.mygroup.mytask", "--no_edit"])

        assert result.exit_code == 0, f"Failed: {result.output}"
        assert (initialized_vault / "myproj.mygroup.md").exists(), "Group should be created"
        assert (initialized_vault / "myproj.mygroup.mytask.md").exists(), "Task should be created"

    def test_new_project_rejects_dots(self, runner, initialized_vault, monkeypatch):
        """Project names cannot contain dots."""
        monkeypatch.chdir(initialized_vault)

        result = runner.invoke(cli, ["new", "project", "my.project", "--no_edit"])
        assert result.exit_code != 0, "Should reject project name with dots"

    def test_new_note_under_project(self, runner, initialized_vault, monkeypatch):
        """cor new note project.notename should create note under project."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        result = runner.invoke(cli, ["new", "note", "myproj.meeting", "--no_edit"])

        assert result.exit_code == 0, f"New note failed: {result.output}"
        assert (initialized_vault / "myproj.meeting.md").exists()

        content = (initialized_vault / "myproj.meeting.md").read_text()
        assert "type: note" in content, "Note should have type: note"


class TestStatus:
    """Test cor status command."""

    def test_status_shows_overdue(self, runner, initialized_vault, monkeypatch):
        """cor daily should show overdue tasks."""
        monkeypatch.chdir(initialized_vault)

        # Create a task with past due date
        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.overdue", "--no_edit"])

        task_path = initialized_vault / "myproj.overdue.md"
        content = task_path.read_text()
        content = content.replace("due:", "due: 2020-01-01")
        task_path.write_text(content)

        result = runner.invoke(cli, ["daily"])
        assert "Overdue" in result.output or "overdue" in result.output.lower()


class TestProjects:
    """Test cor projects command."""

    def test_projects_lists_projects(self, runner, initialized_vault, monkeypatch):
        """cor projects should list all projects."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "proj1", "--no_edit"])
        runner.invoke(cli, ["new", "project", "proj2", "--no_edit"])

        result = runner.invoke(cli, ["projects"])
        assert result.exit_code == 0
        assert "Proj1" in result.output or "proj1" in result.output.lower()
        assert "Proj2" in result.output or "proj2" in result.output.lower()

    def test_projects_shows_status(self, runner, initialized_vault, monkeypatch):
        """cor projects should show project status."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        
        result = runner.invoke(cli, ["projects"])
        assert "planning" in result.output.lower(), "Should show planning status" 


class TestTree:
    """Test cor tree command."""

    def test_tree_shows_tasks(self, runner, initialized_vault, monkeypatch):
        """cor tree should show project tasks."""
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task2", "--no_edit"])

        result = runner.invoke(cli, ["tree", "myproj"])
        assert result.exit_code == 0, f"Tree failed: {result.output}"
        assert "Task1" in result.output or "task1" in result.output.lower()
        assert "Task2" in result.output or "task2" in result.output.lower()

    def test_tree_shows_nested_tasks(self, runner, initialized_vault, monkeypatch):
        """cor tree should show nested task groups."""
        monkeypatch.chdir(initialized_vault)
        runner.invoke(cli, ["init", "--yes"])
        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.group.subtask", "--no_edit"])

        result = runner.invoke(cli, ["tree", "myproj"])
        assert result.exit_code == 0
        # Should show group and subtask
        assert "Group" in result.output or "group" in result.output.lower()
        assert "Subtask" in result.output or "subtask" in result.output.lower()


class TestRename:
    """Test cor rename command."""

    def test_rename_project(self, runner, initialized_vault, monkeypatch):
        """cor rename should rename a project and its tasks."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        import subprocess
        subprocess.run(["git", "init"], cwd=initialized_vault, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=initialized_vault, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=initialized_vault, capture_output=True)

        runner.invoke(cli, ["new", "project", "oldname", "--no_edit"])
        runner.invoke(cli, ["new", "task", "oldname.task1", "--no_edit"])

        result = runner.invoke(cli, ["rename", "oldname", "newname"])
        assert result.exit_code == 0, f"Rename failed: {result.output}"

        # Check files renamed
        assert (initialized_vault / "newname.md").exists(), "Project should be renamed"
        assert (initialized_vault / "newname.task1.md").exists(), "Task should be renamed"
        assert not (initialized_vault / "oldname.md").exists(), "Old project should not exist"

    def test_rename_updates_links(self, runner, initialized_vault, monkeypatch):
        """cor rename should update links in parent files."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        import subprocess
        subprocess.run(["git", "init"], cwd=initialized_vault, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=initialized_vault, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=initialized_vault, capture_output=True)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.oldtask", "--no_edit"])

        # Rename task
        result = runner.invoke(cli, ["rename", "myproj.oldtask", "myproj.newtask"])
        assert result.exit_code == 0, f"Rename failed: {result.output}"

        # Check link updated in project
        content = (initialized_vault / "myproj.md").read_text()
        assert "(myproj.newtask)" in content, "Project should link to renamed task"
        assert "(myproj.oldtask)" not in content, "Old link should not exist"

    def test_rename_dry_run(self, runner, initialized_vault, monkeypatch):
        """cor rename --dry-run should preview without changing."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        import subprocess
        subprocess.run(["git", "init"], cwd=initialized_vault, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=initialized_vault, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=initialized_vault, capture_output=True)

        runner.invoke(cli, ["new", "project", "oldname", "--no_edit"])

        result = runner.invoke(cli, ["rename", "oldname", "newname", "--dry-run"])
        assert result.exit_code == 0

        # Files should not be changed
        assert (initialized_vault / "oldname.md").exists(), "Dry run should not rename"
        assert not (initialized_vault / "newname.md").exists()


class TestGroup:
    """Test cor group command."""

    def test_group_creates_group_file(self, runner, initialized_vault, monkeypatch):
        """cor group should create a new group file."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task2", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.refactor", "task1", "task2"])
        assert result.exit_code == 0, f"Group failed: {result.output}"

        # Check group file created
        assert (initialized_vault / "myproj.refactor.md").exists(), "Group file should be created"

    def test_group_moves_tasks(self, runner, initialized_vault, monkeypatch):
        """cor group should move tasks under the group."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task2", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup", "task1", "task2"])
        assert result.exit_code == 0, f"Group failed: {result.output}"

        # Check tasks renamed
        assert (initialized_vault / "myproj.mygroup.task1.md").exists(), "Task1 should be under group"
        assert (initialized_vault / "myproj.mygroup.task2.md").exists(), "Task2 should be under group"
        assert not (initialized_vault / "myproj.task1.md").exists(), "Old task1 should not exist"
        assert not (initialized_vault / "myproj.task2.md").exists(), "Old task2 should not exist"

    def test_group_updates_parent_links(self, runner, initialized_vault, monkeypatch):
        """cor group should update parent links in moved tasks."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup", "task1"])
        assert result.exit_code == 0, f"Group failed: {result.output}"

        # Check parent updated in task
        content = (initialized_vault / "myproj.mygroup.task1.md").read_text()
        assert "parent: myproj.mygroup" in content, "Parent should be updated to group"
        assert "[< Mygroup](myproj.mygroup)" in content, "Back link should point to group"

    def test_group_updates_project_tasks_section(self, runner, initialized_vault, monkeypatch):
        """cor group should add group to project and remove old task entries."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup", "task1"])
        assert result.exit_code == 0, f"Group failed: {result.output}"

        # Check project file
        content = (initialized_vault / "myproj.md").read_text()
        assert "(myproj.mygroup)" in content, "Project should link to group"
        assert "(myproj.task1)" not in content, "Old task link should be removed"

    def test_group_adds_tasks_to_group(self, runner, initialized_vault, monkeypatch):
        """cor group should add task entries to the group file."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task2", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup", "task1", "task2"])
        assert result.exit_code == 0, f"Group failed: {result.output}"

        # Check group file has tasks
        content = (initialized_vault / "myproj.mygroup.md").read_text()
        assert "(myproj.mygroup.task1)" in content, "Group should link to task1"
        assert "(myproj.mygroup.task2)" in content, "Group should link to task2"

    def test_group_dry_run(self, runner, initialized_vault, monkeypatch):
        """cor group --dry-run should preview without changing."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup", "task1", "--dry-run"])
        assert result.exit_code == 0
        assert "Dry Run" in result.output

        # Files should not be changed
        assert (initialized_vault / "myproj.task1.md").exists(), "Dry run should not move task"
        assert not (initialized_vault / "myproj.mygroup.md").exists(), "Dry run should not create group"

    def test_group_requires_project(self, runner, initialized_vault, monkeypatch):
        """cor group should fail if project doesn't exist."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        result = runner.invoke(cli, ["group", "nonexistent.mygroup", "task1"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_group_requires_tasks(self, runner, initialized_vault, monkeypatch):
        """cor group should fail if no tasks specified."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup"])
        assert result.exit_code != 0
        assert "task" in result.output.lower()

    def test_group_validates_task_exists(self, runner, initialized_vault, monkeypatch):
        """cor group should fail if task doesn't exist."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.mygroup", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_group_fails_if_group_exists(self, runner, initialized_vault, monkeypatch):
        """cor group should fail if group already exists."""
        monkeypatch.setenv("CORTEX_VAULT", str(initialized_vault))
        monkeypatch.chdir(initialized_vault)

        runner.invoke(cli, ["new", "project", "myproj", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.existinggroup", "--no_edit"])
        runner.invoke(cli, ["new", "task", "myproj.task1", "--no_edit"])

        result = runner.invoke(cli, ["group", "myproj.existinggroup", "task1"])
        assert result.exit_code != 0
        assert "exists" in result.output.lower()
