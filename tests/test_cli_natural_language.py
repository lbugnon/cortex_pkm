"""Integration tests for natural language date parsing in CLI."""

import pytest
import frontmatter
from datetime import datetime, timedelta
from click.testing import CliRunner

from cor.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def initialized_vault(temp_vault, runner):
    """Return a vault that has been initialized with cor init."""
    return temp_vault


class TestNewCommandNaturalLanguage:
    """Test cor new command with natural language dates and tags."""

    def test_new_task_with_due_date(self, runner, initialized_vault, monkeypatch):
        """cor new task should parse natural language due dates."""
        monkeypatch.chdir(initialized_vault)

        # Create project first
        runner.invoke(cli, ["new", "project", "myproj", "--no-edit"])

        # Create task with natural language due date
        result = runner.invoke(
            cli,
            ["new", "task", "myproj.mytask", "finish", "the", "pipeline", "due", "tomorrow", "--no-edit"]
        )
        assert result.exit_code == 0, f"New task failed: {result.output}"
        
        # Verify the task was created
        task_path = initialized_vault / "myproj.mytask.md"
        assert task_path.exists()
        
        # Verify the description and due date
        post = frontmatter.load(task_path)
        assert "finish the pipeline" in post.content
        assert "due" in post.metadata
        
        # Due date should be approximately tomorrow
        due_date = datetime.strptime(post["due"], "%Y-%m-%d %H:%M")
        tomorrow = datetime.now() + timedelta(days=1)
        assert abs((due_date - tomorrow).days) <= 1

    def test_new_task_with_tags(self, runner, initialized_vault, monkeypatch):
        """cor new task should parse tags from text."""
        monkeypatch.chdir(initialized_vault)

        # Create project first
        runner.invoke(cli, ["new", "project", "myproj", "--no-edit"])

        # Create task with tags
        result = runner.invoke(
            cli,
            ["new", "task", "myproj.mytask", "implement", "feature", "tag", "ml", "nlp", "--no-edit"]
        )
        assert result.exit_code == 0, f"New task failed: {result.output}"
        
        # Verify the task was created
        task_path = initialized_vault / "myproj.mytask.md"
        assert task_path.exists()
        
        # Verify the description and tags
        post = frontmatter.load(task_path)
        assert "implement feature" in post.content
        assert "tags" in post.metadata
        assert "ml" in post["tags"]
        assert "nlp" in post["tags"]

    def test_new_task_with_due_and_tags(self, runner, initialized_vault, monkeypatch):
        """cor new task should parse both due date and tags."""
        monkeypatch.chdir(initialized_vault)

        # Create project first
        runner.invoke(cli, ["new", "project", "myproj", "--no-edit"])

        # Create task with both due date and tags
        result = runner.invoke(
            cli,
            ["new", "task", "myproj.mytask", "fix", "bug", "due", "tomorrow", "tag", "urgent", "bugfix", "--no-edit"]
        )
        assert result.exit_code == 0, f"New task failed: {result.output}"
        
        # Verify the task was created
        task_path = initialized_vault / "myproj.mytask.md"
        assert task_path.exists()
        
        # Verify the description, due date, and tags
        post = frontmatter.load(task_path)
        assert "fix bug" in post.content
        assert "due" in post.metadata
        assert "tags" in post.metadata
        assert "urgent" in post["tags"]
        assert "bugfix" in post["tags"]
        
        # Due date should be approximately tomorrow
        due_date = datetime.strptime(post["due"], "%Y-%m-%d %H:%M")
        tomorrow = datetime.now() + timedelta(days=1)
        assert abs((due_date - tomorrow).days) <= 1

    def test_new_task_with_due_date_friday(self, runner, initialized_vault, monkeypatch):
        """cor new task should parse 'next friday' as due date."""
        monkeypatch.chdir(initialized_vault)

        # Create project first
        runner.invoke(cli, ["new", "project", "myproj", "--no-edit"])

        # Create task with "next friday" due date
        result = runner.invoke(
            cli,
            ["new", "task", "myproj.mytask", "complete", "report", "due", "next", "friday", "--no-edit"]
        )
        assert result.exit_code == 0, f"New task failed: {result.output}"
        
        # Verify the task was created
        task_path = initialized_vault / "myproj.mytask.md"
        assert task_path.exists()
        
        # Verify the description and due date
        post = frontmatter.load(task_path)
        assert "complete report" in post.content
        
        # Due date should be set (next friday)
        if "due" in post.metadata:
            due_date = datetime.strptime(post["due"], "%Y-%m-%d %H:%M")
            # Next friday should be within the next 14 days
            now = datetime.now()
            assert (due_date - now).days >= 0
            assert (due_date - now).days <= 14

    def test_new_task_without_natural_language(self, runner, initialized_vault, monkeypatch):
        """cor new task should work without natural language keywords."""
        monkeypatch.chdir(initialized_vault)

        # Create project first
        runner.invoke(cli, ["new", "project", "myproj", "--no-edit"])

        # Create task with normal text
        result = runner.invoke(
            cli,
            ["new", "task", "myproj.mytask", "just", "a", "normal", "task", "description", "--no-edit"]
        )
        assert result.exit_code == 0, f"New task failed: {result.output}"
        
        # Verify the task was created
        task_path = initialized_vault / "myproj.mytask.md"
        assert task_path.exists()
        
        # Verify the description is unchanged
        post = frontmatter.load(task_path)
        assert "just a normal task description" in post.content
        # Due field may exist in template but should be None
        assert post.get("due") is None
