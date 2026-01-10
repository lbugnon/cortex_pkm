"""Reference management commands for bibliography."""

from pathlib import Path

import click

from ..crossref import lookup_doi, extract_doi_from_url, CrossrefResult
from ..bibtex import add_bib_entry
from ..core.refs import (
    RefMetadata,
    find_refs,
    generate_citekey,
    get_existing_citekeys,
    get_ref_path,
)
from ..utils import get_notes_dir, require_init, log_info, open_in_editor


def _ensure_ref_dir(notes_dir: Path) -> Path:
    """Ensure ref/ directory exists."""
    ref_dir = notes_dir / "ref"
    ref_dir.mkdir(exist_ok=True)
    return ref_dir


def _create_ref_file(
    notes_dir: Path,
    citekey: str,
    result: CrossrefResult,
    tags: list[str] = None,
) -> Path:
    """Create reference markdown file from CrossrefResult."""
    ref_dir = _ensure_ref_dir(notes_dir)
    ref_path = ref_dir / f"{citekey}.md"

    # Build plain markdown content
    authors_str = ", ".join(result.authors) if result.authors else "Unknown"
    abstract = result.abstract or "_Abstract not available._"

    content = f"""# {result.title}

{authors_str}



## Abstract

{abstract}

## Notes

<!-- Your notes about this paper -->

## Key Points

- 

## Quotes

> 
"""

    ref_path.write_text(content)
    return ref_path


@click.command(short_help="Add a reference from DOI or URL")
@click.argument("identifier")
@click.option("--key", "-k", help="Custom citekey (auto-generated if not provided)")
@click.option("--tags", "-t", multiple=True, help="Tags to add to the reference")
@click.option("--no-edit", is_flag=True, help="Don't open in editor after creating")
@require_init
def add(identifier: str, key: str | None, tags: tuple, no_edit: bool):
    """Add a reference from DOI or URL.

    IDENTIFIER can be:
    - A DOI: 10.1234/example.2024
    - A DOI URL: https://doi.org/10.1234/example
    - A publisher URL containing a DOI

    Examples:
        cor ref add 10.1234/example.2024
        cor ref add https://doi.org/10.1234/example
        cor ref add --key smith2024ml 10.1234/example
        cor ref add -t machine-learning -t nlp 10.1234/example
    """
    notes_dir = get_notes_dir()

    # Extract DOI from identifier
    doi = extract_doi_from_url(identifier)
    if not doi:
        doi = identifier.strip()

    # Check if DOI already exists in references.bib
    from ..bibtex import has_doi_in_bib
    existing_citekey = has_doi_in_bib(notes_dir, doi)
    if existing_citekey:
        raise click.ClickException(
            f"Reference with DOI {doi} already exists: {existing_citekey}"
        )

    log_info(f"Looking up DOI: {doi}")

    # Fetch metadata from Crossref
    result = lookup_doi(doi)
    if not result:
        raise click.ClickException(
            f"Could not fetch metadata for DOI: {doi}\n"
            "Please check the DOI is correct and try again."
        )

    # Display found info
    authors_str = "; ".join(result.authors[:3])
    if len(result.authors) > 3:
        authors_str += " et al."

    log_info(f"Found: {result.title}")
    log_info(f"       {authors_str} ({result.year or 'n.d.'})")
    if result.journal:
        log_info(f"       {result.journal}")

    # Generate or validate citekey
    existing_keys = get_existing_citekeys(notes_dir)

    if key:
        # User provided custom key
        if key in existing_keys:
            raise click.ClickException(
                f"Citekey '{key}' already exists. Use a different key."
            )
        citekey = key
    else:
        # Auto-generate
        citekey = generate_citekey(
            result.authors, result.year, result.title, existing_keys
        )

    # Create reference file and add to references.bib
    ref_path = _create_ref_file(notes_dir, citekey, result, list(tags))
    try:
        add_bib_entry(notes_dir, citekey, result)
    except Exception as e:
        log_info(f"Warning: could not update references.bib: {e}")

    log_info(f"Created reference: ref/{citekey}.md")
    log_info("Updated bibliography: ref/references.bib")
    log_info(f"Cite with: [{citekey}](ref/{citekey})")

    # Open in editor unless --no-edit
    if not no_edit:
        open_in_editor(ref_path)


@click.command(short_help="List all references")
@click.option("--format", "-f", "fmt", type=click.Choice(["table", "short"]),
              default="table", help="Output format")
@require_init
def list_refs(fmt: str):
    """List all references in the bibliography.

    Examples:
        cor ref list
        cor ref list --format short
    """
    notes_dir = get_notes_dir()
    refs = find_refs(notes_dir)

    if not refs:
        log_info("No references found. Add one with: cor ref add <doi>")
        return

    # Sort by year (newest first), then by citekey
    refs.sort(key=lambda r: (-(r.year or 0), r.citekey))

    if fmt == "short":
        for ref in refs:
            log_info(ref.citekey)
    else:
        # Table format
        log_info(f"{'Citekey':<25} {'Year':<6} {'Authors':<25} {'Title':<40}")
        log_info("-" * 100)

        for ref in refs:
            authors = ref.authors[0] if ref.authors else "Unknown"
            if len(ref.authors) > 1:
                authors += " et al."
            if len(authors) > 25:
                authors = authors[:22] + "..."

            title = ref.title
            if len(title) > 40:
                title = title[:37] + "..."

            year = str(ref.year) if ref.year else "n.d."

            log_info(f"{ref.citekey:<25} {year:<6} {authors:<25} {title:<40}")

        log_info(f"\nTotal: {len(refs)} references")


@click.command(short_help="Show reference details")
@click.argument("citekey")
@require_init
def show(citekey: str):
    """Display detailed information about a reference.

    Examples:
        cor ref show smith2024neural
    """
    notes_dir = get_notes_dir()
    ref_path = get_ref_path(citekey, notes_dir)

    if not ref_path.exists():
        raise click.ClickException(f"Reference not found: {citekey}")

    from ..core.refs import Reference
    ref = Reference.from_file(ref_path)

    # Display details
    log_info(f"\n{click.style(ref.title, bold=True)}")
    log_info(f"Citekey: {ref.citekey}")
    log_info(f"Type: {ref.entry_type}")
    log_info(f"Year: {ref.year or 'n.d.'}")
    log_info(f"Authors: {', '.join(ref.authors)}")

    if ref.journal:
        log_info(f"Journal: {ref.journal}")
    if ref.doi:
        log_info(f"DOI: {ref.doi}")
    if ref.url:
        log_info(f"URL: {ref.url}")
    if ref.tags:
        log_info(f"Tags: {', '.join(ref.tags)}")

    log_info(f"\nFile: ref/{citekey}.md")
    log_info(f"Cite: [{ref.citekey}](ref/{citekey})")


@click.command(short_help="Edit a reference")
@click.argument("citekey")
@require_init
def edit(citekey: str):
    """Open reference in editor.

    Examples:
        cor ref edit smith2024neural
    """
    notes_dir = get_notes_dir()
    ref_path = get_ref_path(citekey, notes_dir)

    if not ref_path.exists():
        raise click.ClickException(f"Reference not found: {citekey}")

    open_in_editor(ref_path)


@click.command(short_help="Delete a reference")
@click.argument("citekey")
@click.option("--force", "-f", is_flag=True, help="Delete without confirmation")
@require_init
def delete(citekey: str, force: bool):
    """Delete a reference.

    Examples:
        cor ref del smith2024neural
        cor ref del -f smith2024neural
    """
    notes_dir = get_notes_dir()
    ref_path = get_ref_path(citekey, notes_dir)

    if not ref_path.exists():
        raise click.ClickException(f"Reference not found: {citekey}")

    if not force:
        from ..core.refs import Reference
        ref = Reference.from_file(ref_path)
        log_info(f"Delete reference: {ref.title}")
        log_info(f"  Authors: {', '.join(ref.authors)}")
        if not click.confirm("Are you sure?"):
            log_info("Cancelled.")
            return

    ref_path.unlink()
    log_info(f"Deleted: ref/{citekey}")


# Create command group
@click.group()
def ref():
    """Manage bibliography references.

    References are stored as markdown notes in ref/ with BibLaTeX-compatible
    metadata. Each reference can include abstract, user notes, and tags.

    Citation format: [AuthorYear](ref/citekey)
    """
    pass


# Register subcommands
ref.add_command(add)
ref.add_command(list_refs, name="list")
ref.add_command(show)
ref.add_command(edit)
ref.add_command(delete, name="del")
