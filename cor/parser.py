"""Parse markdown files with YAML frontmatter."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from cor.schema import DATE_TIME

import frontmatter


@dataclass
class Note:
    """A parsed markdown note."""

    path: Path
    title: str
    created: Optional[datetime]
    modified: Optional[datetime]
    status: Optional[str]
    due: Optional[date]
    priority: Optional[str]
    note_type: str  # project, task, note
    tags: list[str]
    content: str

    @property
    def is_overdue(self) -> bool:
        if not self.due or self.status == "done":
            return False
        return self.due < datetime.today()

    @property
    def is_due_this_week(self) -> bool:
        if not self.due or self.status == "done":
            return False
        days_until = (self.due - datetime.today()).days
        return 0 <= days_until <= 7

    @property
    def is_stale(self) -> bool:
        if not self.modified or self.status in ("done", "paused", "complete"):
            return False
        days_since = (datetime.today() - self.modified).days
        return days_since > 14

    @property
    def days_overdue(self) -> int:
        """Number of days past due. Returns 0 if not overdue."""
        if not self.is_overdue:
            return 0
        # self.due can be date or datetime, convert to date for comparison
        due_date = self.due if isinstance(self.due, date) and not isinstance(self.due, datetime) else self.due.date() if hasattr(self.due, 'date') else self.due
        return (date.today() - due_date).days

    @property
    def days_since_modified(self) -> int:
        """Days since last modification."""
        if not self.modified:
            return 0
        return (datetime.now() - self.modified).days

    @property
    def parent_project(self) -> str | None:
        """Extract root project name from path (e.g., 'project' from 'project.group.task.md')."""
        from .utils import get_root_project
        return get_root_project(self.path.stem)


def parse_date(value) -> Optional[datetime]:
    """Parse a date from frontmatter in format DATE_TIME, datetime or date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    date_object = datetime.strptime(value, DATE_TIME)    
    return date_object

def parse_note(path: Path) -> Note:
    """Parse a markdown file into a Note object."""
    post = frontmatter.load(path)
    meta = post.metadata

    # Get title from first heading or filename
    title = path.stem
    for line in post.content.split("\n"):
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return Note(
        path=path,
        title=title,
        created=parse_date(meta.get("created")),
        modified=parse_date(meta.get("modified")),
        status=meta.get("status"),
        due=parse_date(meta.get("due")),
        priority=meta.get("priority"),
        note_type=meta.get("type"),
        tags=meta.get("tags", []),
        content=post.content,
    )


def find_notes(notes_dir: Path) -> list[Note]:
    """Find and parse all markdown files in notes directory."""
    notes = []
    for path in notes_dir.glob("*.md"):
        if path.name.startswith("."):
            continue
        try:
            notes.append(parse_note(path))
        except Exception as e:
            # Skip files that can't be parsed
            print(f"Warning: Could not parse {path}: {e}")
    return notes
