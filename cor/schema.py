"""Schema constants for cortex notes.

Reads valid values directly from schema.yaml.
"""
from pathlib import Path
import yaml

# Find schema.yaml relative to repo root
_SCHEMA_PATH = Path(__file__).parent / "assets" / "schema.yaml"


def _load_schema():
    """Load and parse schema.yaml."""
    with open(_SCHEMA_PATH) as f:
        return yaml.safe_load(f)

_SCHEMA = _load_schema()

# Extract valid values as sets for O(1) lookup
VALID_PROJECT_STATUS = set(_SCHEMA["project"]["status"]["values"])
VALID_TASK_STATUS = set(_SCHEMA["task"]["status"]["values"])
VALID_PRIORITY = set(_SCHEMA["common"]["priority"]["values"])

# Status symbols for checkboxes
STATUS_SYMBOLS = {
    "todo": "[ ]",
    "active": "[.]",
    "blocked": "[o]",
    "done": "[x]",
    "dropped": "[~]",
    "waiting": "[/]",
}

DATE_TIME = '%Y-%m-%d %H:%M'

def get_status_symbol(status: str) -> str:
    """Get checkbox symbol for a status."""
    return STATUS_SYMBOLS.get(status, "[ ]")