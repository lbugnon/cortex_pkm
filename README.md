# CortexPKM

Plain text knowledge management. Track projects, tasks, ideas, and progress using markdown files and git.

Small new year project to try Claude Code :)

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

# 2. Initialize git repository (required for automatic date tracking)
git init

# 3. Initialize Cortex vault
# This sets the global vault path and installs git hooks
cor init

# Or create an example vault to explore features
cor example-vault

# Configure vault path (optional - defaults to current directory)
cor config vault ~/notes

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
| `cor init` | Initialize vault (creates notes/, templates, root.md, backlog.md) |
| `cor new <type> <name>` | Create file from template (project, task, note) |
| `cor edit <name>` | Open existing file in editor (use `-a` to include archived) |
| `cor mark <name> <status>` | Change task status (todo, active, blocked, done, dropped) |
| `cor sync` | Pull, commit all changes, and push to remote |
| `cor daily` | Show today's tasks and agenda |
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
| `cor config set vault <path>` | Set global vault path |
| `cor config show` | Show current configuration |
| `cor maintenance sync` | Manually run archive/status sync |

## Configuration

### Vault Path Setup

Cortex requires your vault path to be configured in `~/.config/cortex/config.yaml`. This is set automatically by `cor init`, but can be changed anytime:

```bash
# Set during initial setup
cor init

# Or reconfigure later
cor config set vault /path/to/notes
```

Once configured, you can run `cor` commands from any directory:

```bash
# Commands work from anywhere after init
cd /tmp
cor status              # Uses configured vault
cor new task my-project.quick-idea
cor daily
```

### Config File Format

`~/.config/cortex/config.yaml`:

```yaml
vault: /home/user/notes        # Vault path (required)
verbosity: 1                   # 0=silent, 1=normal, 2=verbose, 3=debug
```

### Configuration Commands

```bash
cor config show              # Display current config
cor config set vault <path>  # Set vault path
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

### Installation
````

Run once to install git hooks and enable shell completion:

```bash
cor hooks install
```

This installs:
- Git pre-commit hook (auto-updates modified dates, archives completed items, validates consistency)
- Shell completion script to your conda environment (if using conda)

### Zsh Configuration

**Important:** Do NOT manually run `compinit` after `cor hooks install`. The completion script handles initialization automatically.

Add to your `~/.zshrc` to enable Tab cycling through suggestions:

```zsh
# Enable Tab to cycle through completion matches (recommended)
bindkey '^I' menu-complete
bindkey '^[[Z' reverse-menu-complete  # Shift-Tab for reverse
```

Then reactivate your environment:
```zsh
conda deactivate
conda activate <your-env-name>
```

**Test it:**
```zsh
cor edit diffusion<TAB>           # Shows matching files
<TAB> again                        # Cycles to next match
```

### Bash Configuration

Bash completion is automatically enabled. Add to your `~/.bashrc` for menu-style cycling:

```bash
# Show all completions on first Tab, cycle on subsequent Tabs
bind 'set show-all-if-ambiguous on'
bind 'TAB:menu-complete'
bind '"\e[Z": reverse-menu-complete'  # Shift-Tab for reverse
```

Then reload:
```bash
source ~/.bashrc
```

**Test it:**
```bash
cor edit diffusion<TAB>           # Shows matching files
<TAB> again                        # Cycles to next match
```

### Tab Completion Examples

Once set up:

```bash
cor new task my-<TAB>              # Completes project names
cor edit dif<TAB>                  # Fuzzy matches + cycles
cor mark impl <TAB>                # Shows task status options
```

## Directory Structure

### User Configuration & Vault

```
~/.config/cortex/
└── config.yaml             # Global config (vault path, verbosity)

~/.miniconda3/etc/conda/activate.d/
└── cor-completion.sh       # Shell completion (zsh & bash)

your-vault/                 # Your notes directory
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

The pre-commit hook automatically runs on every commit to keep your vault consistent.

### Installation

```bash
cor hooks install    # Enable pre-commit hook + shell completion
cor hooks uninstall  # Disable pre-commit hook
```

The hook is automatically installed when you run `cor init` in a git repository.

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
