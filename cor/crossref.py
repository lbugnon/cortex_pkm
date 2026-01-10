"""Crossref API integration for bibliography references.

Uses habanero library to fetch paper metadata from DOIs.
"""

import re
from dataclasses import dataclass
from typing import Optional

from habanero import Crossref


@dataclass
class CrossrefResult:
    """Structured result from Crossref lookup."""

    title: str
    authors: list[str]  # "Last, First" format
    year: Optional[int]
    doi: str
    journal: Optional[str]
    volume: Optional[str]
    pages: Optional[str]
    publisher: Optional[str]
    abstract: Optional[str]
    entry_type: str  # BibLaTeX type: article, book, etc.
    url: Optional[str]


# Mapping from Crossref types to BibLaTeX entry types
CROSSREF_TYPE_MAP = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book": "book",
    "book-chapter": "incollection",
    "monograph": "book",
    "report": "techreport",
    "dissertation": "phdthesis",
    "dataset": "misc",
    "posted-content": "unpublished",  # preprints
    "peer-review": "misc",
}


def _format_author(author: dict) -> str:
    """Format author dict to 'Last, First' string."""
    family = author.get("family", "")
    given = author.get("given", "")
    if family and given:
        return f"{family}, {given}"
    return family or given or "Unknown"


def _extract_year(item: dict) -> Optional[int]:
    """Extract publication year from Crossref item."""
    # Try different date fields
    for field in ["published-print", "published-online", "created", "issued"]:
        if field in item:
            date_parts = item[field].get("date-parts", [[]])
            if date_parts and date_parts[0]:
                return date_parts[0][0]
    return None


def _clean_abstract(abstract: Optional[str]) -> Optional[str]:
    """Clean HTML tags from abstract."""
    if not abstract:
        return None
    # Remove JATS XML tags
    clean = re.sub(r"<[^>]+>", "", abstract)
    # Normalize whitespace
    clean = " ".join(clean.split())
    return clean if clean else None


def lookup_doi(doi: str) -> Optional[CrossrefResult]:
    """Fetch metadata from Crossref for a DOI.

    Args:
        doi: Digital Object Identifier (with or without prefix)

    Returns:
        CrossrefResult with paper metadata, or None if not found
    """
    # Clean DOI - remove URL prefixes
    doi = extract_doi_from_url(doi) or doi
    doi = doi.strip()

    try:
        cr = Crossref()
        result = cr.works(ids=doi)

        if not result or "message" not in result:
            return None

        item = result["message"]

        # Extract title
        titles = item.get("title", [])
        title = titles[0] if titles else "Untitled"

        # Extract authors
        authors = [_format_author(a) for a in item.get("author", [])]
        if not authors:
            authors = ["Unknown"]

        # Extract year
        year = _extract_year(item)

        # Extract journal/container
        containers = item.get("container-title", [])
        journal = containers[0] if containers else None

        # Map type
        cr_type = item.get("type", "misc")
        entry_type = CROSSREF_TYPE_MAP.get(cr_type, "misc")

        # Extract other fields
        volume = item.get("volume")
        pages = item.get("page")
        publisher = item.get("publisher")
        abstract = _clean_abstract(item.get("abstract"))
        url = item.get("URL")

        return CrossrefResult(
            title=title,
            authors=authors,
            year=year,
            doi=item.get("DOI", doi),
            journal=journal,
            volume=volume,
            pages=pages,
            publisher=publisher,
            abstract=abstract,
            entry_type=entry_type,
            url=url,
        )

    except Exception as e:
        # API errors, network issues, etc.
        print(f"Crossref lookup failed: {e}")
        return None


def search_crossref(query: str, limit: int = 10) -> list[CrossrefResult]:
    """Search Crossref for papers matching query.

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of CrossrefResult objects
    """
    try:
        cr = Crossref()
        results = cr.works(query=query, limit=limit)

        if not results or "message" not in results:
            return []

        items = results["message"].get("items", [])

        parsed = []
        for item in items:
            titles = item.get("title", [])
            title = titles[0] if titles else "Untitled"

            authors = [_format_author(a) for a in item.get("author", [])]
            if not authors:
                authors = ["Unknown"]

            year = _extract_year(item)

            containers = item.get("container-title", [])
            journal = containers[0] if containers else None

            cr_type = item.get("type", "misc")
            entry_type = CROSSREF_TYPE_MAP.get(cr_type, "misc")

            parsed.append(CrossrefResult(
                title=title,
                authors=authors,
                year=year,
                doi=item.get("DOI", ""),
                journal=journal,
                volume=item.get("volume"),
                pages=item.get("page"),
                publisher=item.get("publisher"),
                abstract=_clean_abstract(item.get("abstract")),
                entry_type=entry_type,
                url=item.get("URL"),
            ))

        return parsed

    except Exception as e:
        print(f"Crossref search failed: {e}")
        return []


def extract_doi_from_url(url: str) -> Optional[str]:
    """Extract DOI from various URL formats.

    Handles:
    - https://doi.org/10.1234/example
    - https://dx.doi.org/10.1234/example
    - http://example.com/10.1234/example
    - 10.1234/example (plain DOI)

    Returns:
        Extracted DOI or None if not found
    """
    if not url:
        return None

    url = url.strip()

    # Plain DOI pattern
    doi_pattern = r"(10\.\d{4,}/[^\s]+)"

    # Try to extract from URL
    match = re.search(doi_pattern, url)
    if match:
        doi = match.group(1)
        # Clean trailing punctuation
        doi = doi.rstrip(".,;")
        return doi

    return None
