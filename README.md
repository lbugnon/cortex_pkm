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

Cortex can be used from any directory once you configure a vault path.

### Vault Path Resolution

Cortex finds your vault in this order:

1. **`CORTEX_VAULT` environment variable** - Highest priority
2. **Config file** (`~/.config/cortex/config.yaml`) - Set via `cor config set vault`
3. **Current directory** - Fallback if nothing else is configured

### Setting Up Global Access

```bash
# Set your vault path once
cor config set vault ~/notes

# Now you can run commands from anywhere
cd /tmp
cor status           # Works! Uses ~/notes
cor new task my-project.quick-idea
```

### Configuration Commands

```bash
cor config show      # See current config and vault resolution
cor config set vault /path/to/notes  # Set vault path
```

### Environment Variable

For temporary overrides or CI/CD:

```bash
export CORTEX_VAULT=/path/to/notes
cor status  # Uses the env var
```

### File Hierarchy and Links

Cortex uses dot notation for hierarchy: `project.group.task.md`

**Forward links** (in parent files):
```markdown
## Tasks
- [ ] [Task name](project.task)
- [.] [Group name](project.group)
```

**Backlinks** (in child files):
```markdown
[< Parent Name](parent)
```

These are relative paths. For example if a task is archived while parent is not, backlink will be `[< Parent](../parent)`

### Moving Files Between Parents

Use `cor rename` or `cor move` to safely rename or move files. When moving a task/group to a different parent (e.g., `p1.task` → `p2.task`), it automatically:

- Removes link from old parent (`p1.md`)
- Adds link to new parent (`p2.md`)
- Updates backlink with new parent title
- Updates `parent` field in frontmatter
- Updates all children's parent references

```bash
cor rename old-project new-project           # Rename project + all tasks
cor rename project.old-task project.new-task # Rename single task
cor move p1.experiments p2.experiments       # Move group to different project
cor rename old-project new-project --dry-run # Preview changes
```

## Shell Setup

### Installation

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
bindkey '\e[Z]' reverse-menu-complete  # Shift-Tab for reverse

# Alternative: arrow-key selection menu (optional)
# zmodload zsh/complist
# zstyle ':completion:*:*:cor:*' menu select
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

```
~/.config/cortex/
└── config.yaml             # Global config (vault path)

your-vault/                 # Your notes directory
├── root.md
├── backlog.md
├── archive/                # Completed items
└── templates/
    ├── project.md
    ├── task.md
    └── note.md

cortex/                     # CLI source (development)
├── cor/
│   ├── cli.py
│   ├── config.py           # Vault path resolution
│   ├── parser.py
│   ├── schema.py
│   └── hooks/
│       └── pre-commit
├── schema.yaml
├── pyproject.toml
└── README.md
```

## Git Hooks

The pre-commit hook runs on every commit and:

1. **Validates frontmatter** - Checks status/priority values against schema
2. **Validates consistency** - Blocks orphan files, broken links, partial renames
3. **Updates modified dates** - Sets `modified` to current timestamp (YYYY-MM-DD HH:MM)
4. **Handles file renames** - Updates parent links, backlinks, and frontmatter when moving files
5. **Unarchives reactivated items** - Moves back from archive when status changes from done
6. **Archives completed items** - Moves to `notes/archive/` when `status: done`
7. **Updates task group status** - Calculates group status from children (blocked > active > done > todo)
8. **Updates project status** - Sets project to `active` when any task is active, back to `planning` when none
9. **Syncs task status** - Updates checkboxes in parent: `[ ]` `[.]` `[o]` `[/]` `[x]` `[~]`
10. **Sorts tasks** - Orders by status (blocked, active, waiting, todo, then done, dropped)
11. **Adds separators** - Inserts `---` between active and completed tasks

```bash
cor hooks install    # Enable
cor hooks uninstall  # Disable
```

### Consistency Checks

The hook blocks commits with:

| Issue | Example | Fix |
|-------|---------|-----|
| Broken link | `[Task] (missing-file)` | Fix link or create target |
