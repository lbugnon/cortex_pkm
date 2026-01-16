"""Search and completion functionality for Cortex PKM.

This package contains:
- fuzzy.py: Fuzzy matching
- completion.py: Consolidated shell completion logic
"""

from .fuzzy import (
    fuzzy_match,
    resolve_file_fuzzy,
    resolve_task_fuzzy,
    get_file_path,
    get_task_file_stems,
)

__all__ = [
    "fuzzy_match",
    "resolve_file_fuzzy",
    "resolve_task_fuzzy",
    "get_file_path",
    "get_task_file_stems",
]
