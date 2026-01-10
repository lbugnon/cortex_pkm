"""Reference data models for bibliography management.

References are stored in ref/<citekey>.md files.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import frontmatter

from ..schema import DATE_TIME


@dataclass
class RefMetadata:
    """Lightweight reference metadata for operations."""

    path: Path
    citekey: str
    title: str
    authors: list[str] = field(default_factory=list)  # "Last, First" format
    year: Optional[int] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    entry_type: str = "misc"  # article, book, inproceedings, etc.
    url: Optional[str] = None
    abstract: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    @classmethod
    def from_file(cls, path: Path) -> "RefMetadata":
        """Parse reference from markdown file."""
        post = frontmatter.load(path)
        meta = post.metadata

        # Extract citekey from filename
        citekey = path.stem

        # Parse dates
        created = _parse_date(meta.get("created"))
        modified = _parse_date(meta.get("modified"))

        return cls(
            path=path,
            citekey=citekey,
            title=meta.get("title", citekey),
            authors=meta.get("authors", []),
            year=meta.get("year"),
            doi=meta.get("doi"),
            journal=meta.get("journal"),
            volume=meta.get("volume"),
            pages=meta.get("pages"),
            publisher=meta.get("publisher"),
            entry_type=meta.get("entry_type", "misc"),
            url=meta.get("url"),
            abstract=meta.get("abstract"),
            tags=meta.get("tags", []),
            created=created,
            modified=modified,
        )

    def to_dict(self) -> dict:
        """Convert to dict for frontmatter."""
        data = {
            "type": "ref",
            "entry_type": self.entry_type,
            "citekey": self.citekey,
            "title": self.title,
            "authors": self.authors,
        }

        # Add optional fields if present
        if self.year:
            data["year"] = self.year
        if self.doi:
            data["doi"] = self.doi
        if self.journal:
            data["journal"] = self.journal
        if self.volume:
            data["volume"] = self.volume
        if self.pages:
            data["pages"] = self.pages
        if self.publisher:
            data["publisher"] = self.publisher
        if self.url:
            data["url"] = self.url
        if self.tags:
            data["tags"] = self.tags
        if self.created:
            data["created"] = self.created.strftime(DATE_TIME)
        if self.modified:
            data["modified"] = self.modified.strftime(DATE_TIME)

        return data


@dataclass
class Reference(RefMetadata):
    """Full reference with user notes content."""

    content: str = ""

    @classmethod
    def from_file(cls, path: Path) -> "Reference":
        """Full parsing including content."""
        post = frontmatter.load(path)
        meta = post.metadata

        citekey = path.stem

        created = _parse_date(meta.get("created"))
        modified = _parse_date(meta.get("modified"))

        return cls(
            path=path,
            citekey=citekey,
            title=meta.get("title", citekey),
            authors=meta.get("authors", []),
            year=meta.get("year"),
            doi=meta.get("doi"),
            journal=meta.get("journal"),
            volume=meta.get("volume"),
            pages=meta.get("pages"),
            publisher=meta.get("publisher"),
            entry_type=meta.get("entry_type", "misc"),
            url=meta.get("url"),
            abstract=meta.get("abstract"),
            tags=meta.get("tags", []),
            created=created,
            modified=modified,
            content=post.content,
        )


def _parse_date(value) -> Optional[datetime]:
    """Parse date from frontmatter."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(value, DATE_TIME)
    except (ValueError, TypeError):
        return None


def find_refs(notes_dir: Path, metadata_only: bool = True) -> list:
    """Find all reference files in ref/ subdirectory.

    Args:
        notes_dir: Notes directory path
        metadata_only: If True, return RefMetadata (fast). If False, return Reference.

    Returns:
        List of RefMetadata or Reference instances
    """
    ref_dir = notes_dir / "ref"
    if not ref_dir.exists():
        return []

    refs = []
    for path in ref_dir.glob("*.md"):
        if path.name.startswith("."):
            continue
        try:
            if metadata_only:
                refs.append(RefMetadata.from_file(path))
            else:
                refs.append(Reference.from_file(path))
        except Exception as e:
            print(f"Warning: Could not parse {path}: {e}")

    return refs


def get_existing_citekeys(notes_dir: Path) -> set[str]:
    """Get set of existing citekeys."""
    ref_dir = notes_dir / "ref"
    if not ref_dir.exists():
        return set()

    return {p.stem for p in ref_dir.glob("*.md") if not p.name.startswith(".")}


def generate_citekey(
    authors: list[str],
    year: Optional[int],
    title: str,
    existing_keys: set[str],
) -> str:
    """Generate unique citekey in author<year><keyword> format.

    Examples:
        - smith2024neural
        - jones2023
        - smith2024neural2 (if smith2024neural exists)
    """
    # Extract first author's last name
    if authors:
        first_author = authors[0]
        # Handle "Last, First" format
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            # Handle "First Last" format
            parts = first_author.split()
            last_name = parts[-1] if parts else "unknown"
    else:
        last_name = "unknown"

    # Clean last name
    last_name = re.sub(r"[^a-zA-Z]", "", last_name).lower()
    if not last_name:
        last_name = "unknown"

    # Extract keyword from title
    title_words = re.findall(r"[a-zA-Z]+", title.lower())
    # Skip common words
    skip_words = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with"}
    keyword = ""
    for word in title_words:
        if word not in skip_words and len(word) > 2:
            keyword = word
            break

    # Build base citekey
    year_str = str(year) if year else ""
    base_key = f"{last_name}{year_str}{keyword}"

    # Ensure uniqueness
    if base_key not in existing_keys:
        return base_key

    # Add numeric suffix
    suffix = 2
    while f"{base_key}{suffix}" in existing_keys:
        suffix += 1

    return f"{base_key}{suffix}"


def get_ref_path(citekey: str, notes_dir: Path) -> Path:
    """Get path for a reference file."""
    return notes_dir / "ref" / f"{citekey}.md"
