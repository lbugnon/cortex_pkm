# CortexPKM

Plain text knowledge management. Track projects, tasks, ideas, and progress using markdown files and git.

Small new year project to try new coding agents :)

## Philosophy

- **Plain text + git + minimal tooling** - Simple, using open formats. 
- **Writing is thinking** - Tools assist, not replace. The editor is the main interface. The writing and thinking should be the main driver to organize the content.
- **Files over folders** - Flat structure with dot notation (`project.group.task.md`). `archive` folder serve to hide unactive files. 

## Installation

```bash
pip install -e .
```

## Development

```bash
pip install -e ".[dev]"  # Install with test dependencies
pytest                   # Run all tests
pytest tests/test_cli.py # Run CLI tests only
pytest tests/test_precommit.py # Run pre-commit hook tests
pytest -v                # Verbose output
```

### Test Coverage

The test suite covers:
- **CLI commands**: `init`, `new`, `edit`, `mark`, `sync`, `projects`, `tree`, (`rename` | `move`)
- **Pre-commit hook**: Status sync, archiving, unarchiving, task groups, separators
- **Edge cases**: Multi-task commits, group status propagation, link updates

## Quick Start

```bash
# 1. Create a directory for your vault
mkdir ~/notes
cd ~/notes

# 2. Initialize Cortex vault
# This creates the vault structure, initializes git, and installs git hooks
cor init

# Or create an example vault to explore features
cor example-vault

# Create a new project
cor new project my-project

# Create a task under a project (use dot notation + tab completion)
cor new task my-project.implement-feature

# Create a standalone note
cor new note meeting-notes

# Check what needs attention
cor daily

# Summarize recent work
cor weekly

# Git sync
cor sync
```

## File Types

| Pattern | Type | Purpose |
|---------|------|---------|
| `project.md` | Project | Main project file with goals, scope, done criteria |
| `project.task.md` | Task | Actionable item within a project |
| `project.group.md` | Task Group | Organizes related tasks (also a task itself) |
| `project.group.task.md` | Task | Nested task under a task group |
| `project.group.smaller_group.task.md` | Task | Deeply nested task (supports any depth) |
| `project.note.md` | Note | Reference/thinking, not actionable |
| `backlog.md` | Backlog | Unsorted inbox for capture |
| `root.md` | Root | Dashboard/digest of current state |

## Metadata Reference

All files use YAML frontmatter. See `schema.yaml` for full specification.

### Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `created` | date | Auto-set by `cor new` |
| `modified` | date | Auto-updated by git hook |
| `due` | date | Deadline (optional) |
| `priority` | enum | `low` \| `medium` \| `high` |
| `tags` | list | Freeform tags |

### Project Status

| Value | Description |
|-------|-------------|
| `planning` | Defining goals/scope |
| `active` | Currently being worked on |
| `paused` | Temporarily on hold |
| `done` | Done, goals achieved |

### Task Status

| Value | Symbol | Description |
|-------|--------|-------------|
| `todo` | `[ ]` | Ready to start |
| `active` | `[.]` | Currently in progress |
| `blocked` | `[o]` | Blocked, cannot proceed |
| `waiting` | `[/]` | Waiting on external input (other people/AIs) |
| `done` | `[x]` | Completed (archived) |
| `dropped` | `[~]` | Cancelled/abandoned |

### Example

```yaml
---
created: 2025-12-30
modified: 2025-12-30
status: active
due: 2025-01-15
priority: high
tags: [coding, urgent]
---
```

## Commands

| Command | Description |
|---------|-------------|
| `cor init` | Initialize vault (creates structure, initializes git, installs hooks) |
| `cor new <type> <name>` | Create file from template (project, task, note) |
| `cor edit <name>` | Open existing file in editor (use `-a` to include archived) |
| `cor mark <name> <status>` | Change task status (todo, active, blocked, done, dropped) |
| `cor sync` | Pull, commit all changes, and push to remote |
| `cor daily [tag]` | Show today's tasks; when `tag` is provided, only tasks matching the tag (by project name, task tags, or project tags) |
| `cor weekly` | Show this week's summary |
| `cor projects` | List active projects with status and last activity (from children) |
| `cor tree <project>` | Show task tree for a project with status symbols |
| `cor review` | Interactive review of stale/blocked items |
| `cor rename <old> <new>` | Rename project/task with all dependencies |
| `cor move <old> <new>` | Alias of rename (conceptually better for moving groups/tasks) |
| `cor group <project.group> <tasks>` | Group existing tasks under a new task group |
| `cor process` | Process backlog items into projects |
| `cor hooks install` | Install pre-commit hook and shell completion |
| `cor hooks uninstall` | Remove git hooks |
| `cor config vault <path>` | Set global vault path |
| `cor config` | Show current configuration |
| `cor maintenance sync` | Manually run archive/status sync |

### References (Bibliography)

Manage bibliography as markdown notes in `ref/` and a BibLaTeX file `ref/references.bib`.

- **Add**: Add a reference from a DOI or URL.
   - Command: `cor ref add <identifier> [--key KEY] [--tags TAG ...] [--no-edit]`
   - Identifier can be:
      - A DOI: `10.xxxx/abcd.2024`
      - A DOI URL: `https://doi.org/10.xxxx/abcd.2024` or publisher paths containing a DOI (e.g., `https://www.biorxiv.org/content/10.1101/...`)
      - An arXiv URL or ID: `https://arxiv.org/abs/1706.03762` or `1706.03762` (mapped to `10.48550/arXiv.<id>`)
   - Behavior: creates `ref/<citekey>.md` and updates `ref/references.bib`.
   - Note: does not scrape publisher pages. If the URL does not contain a DOI, a friendly error explains how to supply one.

- **List**: Show all references.
   - Command: `cor ref list [--format table|short]`

- **Show**: Display details for a reference.
   - Command: `cor ref show <citekey>`

- **Edit**: Open the reference note.
   - Command: `cor ref edit <citekey>`

- **Delete**: Remove the reference note.
   - Command: `cor ref del <citekey> [--force]`

- **Search** (experimental): Text search across stored reference metadata.
   - Command: `cor ref search <query> [--limit N]`

Examples:

```bash
# Add from DOI
cor ref add 10.1101/2025.07.24.666581

# Add from DOI URL
cor ref add https://doi.org/10.1101/2025.07.24.666581

# Add from publisher URL (DOI embedded in path)
cor ref add https://www.biorxiv.org/content/10.1101/2025.07.24.666581v1

# Add from arXiv ID
cor ref add 1706.03762

# Custom citekey and tags
cor ref add 10.1101/2025.07.24.666581 --key smith2026transformers --tags ml --tags nlp
```

## Configuration

### Vault Path Setup

Cortex automatically configures your vault path in `~/.config/cortex/config.yaml` when you run `cor init`. You can change it anytime:

```bash
# Set during initial setup
cor init

# Or reconfigure later
cor config vault /path/to/notes
```

Once configured, you can run `cor` commands from any directory:

```bash
# Commands work from anywhere after init
cd /tmp
cor daily
cor new task my-project.quick-idea
```

### Config File Format

`~/.config/cortex/config.yaml`:

```yaml
vault: /home/user/notes        # Vault path (required)
verbosity: 1                   # 0=silent, 1=normal, 2=verbose, 3=debug
```

### Configuration Commands

```bash
cor config                # Display current config
cor config vault <path>   # Set vault path
cor config verbosity <0-3> # Set verbosity level
```

### File Hierarchy & Linking

Cortex uses **dot notation** for hierarchy: `project.group.task.md`

**Forward links** (parent → children):
```markdown
## Tasks
- [ ] [Implement API](project.implement-api)
- [.] [Testing group](project.testing)
```

**Backlinks** (child → parent):
```markdown
[< Project Name](project)
```

Links use **relative paths** to maintain compatibility when files are archived:
- Active child → Active parent: `[< Parent](parent)`
- Archived child → Active parent: `[< Parent](../parent)`
- Active child → Archived parent: Not typical, but supported

### Renaming & Moving Files

Use `cor rename` or `cor move` to safely refactor your vault. The hook automatically:
- Updates all forward links in parents
- Updates all backlinks in children  
- Updates `parent` field in child frontmatter
- Updates all descendants' parent chains
- Moves files to/from archive as needed

```bash
# Rename a project (updates all tasks)
cor rename old-project new-project

# Rename a task
cor rename project.old-task project.new-task

# Move a group to a different project
cor move p1.experiments p2.experiments

# Preview changes before committing
cor rename old-project new-project --dry-run

# Commit the changes
git add -A && git commit -m "Rename project"
```

### Completion Configuration

Control fuzzy completion behavior via environment variable:

```bash
# Allow cycling through all 100%-score matches (default, recommended)
export COR_COMPLETE_COLLAPSE_100=0

# Collapse to shortest match only (faster single-result completion)
export COR_COMPLETE_COLLAPSE_100=1
```

## Shell Setup

Shell completion is automatically configured when you run `cor init`. The setup detects your shell (zsh or bash) and adds the necessary completion code to your shell config file.

### Zsh

After running `cor init`, optionally add to your `~/.zshrc` to enable Tab cycling through suggestions:

Then reload:
```zsh
source ~/.zshrc # or .bashrc
```

## Directory Structure

### User Configuration & Vault

```
~/.config/cortex/
└── config.yaml             # Global config (vault path, verbosity)

~/.zshrc or ~/.bashrc       # Shell completion automatically added here

your-vault/                 # Your notes directory
├── .git/                   # Git repository (auto-initialized by cor init)
│   └── hooks/
│       └── pre-commit      # Auto-maintenance hook
├── root.md                 # Dashboard/digest of current state
├── backlog.md              # Unsorted inbox for capture
├── archive/                # Completed/archived items
│   ├── old-project.md
│   ├── project.old-task.md
│   └── ...
└── templates/              # File templates
    ├── project.md
    ├── task.md
    └── note.md
```

### Project Source (Development)

```
cortex_pkm/                 # Repository root
├── cor/                    # Main package
│   ├── __init__.py
│   ├── cli.py              # Command-line interface
│   ├── config.py           # Vault path resolution
│   ├── parser.py           # YAML/markdown parsing
│   ├── schema.py           # Data schema & validation
│   ├── utils.py            # Utility functions
│   ├── completions.py      # Shell completion logic
│   ├── fuzzy.py            # Fuzzy matching for search
│   ├── maintenance.py      # Auto-sync & archiving
│   ├── commands/           # Command implementations
│   │   ├── __init__.py
│   │   ├── process.py      # Backlog processing
│   │   ├── refactor.py     # Rename/move operations
│   │   └── status.py       # Status display
│   ├── hooks/              # Git integration
│   │   └── pre-commit      # Pre-commit hook script
│   └── assets/             # Built-in templates & schema
│       ├── schema.yaml
│       ├── project.md
│       ├── task.md
│       ├── note.md
│       ├── backlog.md
│       └── root.md
├── tests/                  # Test suite
│   ├── conftest.py         # Test configuration
│   ├── test_cli.py         # CLI command tests
│   ├── test_delete.py      # Delete operation tests
│   ├── test_maintenance.py # Hook & sync tests
│   ├── test_precommit.py   # Pre-commit hook tests
│   ├── test_rename_*.py    # Rename/move tests
│   └── __pycache__/
├── pyproject.toml          # Project config & dependencies
├── README.md               # This file
├── LICENSE                 # MIT License
└── MANIFEST.in             # Package manifest
```

## Git Hooks & Automation

The pre-commit hook automatically runs on every commit to keep your vault consistent. It is automatically installed when you run `cor init`.

### What the Hook Does

**Validation & Consistency:**
1. Validates frontmatter - Checks status/priority values against schema
2. Detects broken links - Blocks commits with missing link targets
3. Prevents orphan files - Files must have valid parent references
4. Detects partial renames - Ensures all related files are renamed together

**Automatic Updates:**
5. Updates modified dates - Sets `modified` field to current timestamp (YYYY-MM-DD HH:MM)
6. Handles file renames - When you rename a file:
   - Updates all parent links (adds/removes task entries)
   - Updates all child parent references
   - Updates backlinks with new parent title
   - Preserves link semantics (relative paths for archive)
7. Archives completed items - Moves to `archive/` when `status: done`
8. Unarchives reactivated items - Moves back from archive when status changes from done
9. Syncs task status - Updates parent checkboxes to match task status:
   - `[ ]` = todo, `[.]` = active, `[o]` = blocked, `[/]` = waiting, `[x]` = done, `[~]` = dropped

**Hierarchy & Organization:**
10. Updates task group status - Calculates from children (blocked > active > done > todo)
11. Updates project status - Sets to `active` if any task is active, back to `planning` when none
12. Sorts tasks - By status (blocked, active, waiting, todo, then done, dropped)
13. Adds separators - Inserts `---` between active and completed tasks for readability

### How It Works

The hook uses `git diff --cached` to detect changes, so it only processes modified files:

```bash
git add my-project.task.md         # Stage changes
git commit -m "Update task"        # Hook runs automatically
```

### Disabling Temporarily

```bash
git commit --no-verify -m "Skip hook"  # Bypass hook for this commit
```

### Manual Sync

To manually run the sync logic on all files (useful after bulk edits):

```bash
cor maintenance sync        # Preview changes
cor maintenance sync --all  # Sync all files (not just modified)
```
