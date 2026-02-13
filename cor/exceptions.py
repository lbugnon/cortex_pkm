"""Custom exception hierarchy for CortexPKM.

This module defines all custom exceptions used throughout the codebase.
CLI commands catch these and format them nicely for the user.
"""


class CortexError(Exception):
    """Base exception for all CortexPKM errors."""
    pass


class ValidationError(CortexError):
    """Data validation failed (invalid metadata, malformed files, etc.)."""
    pass


class NotFoundError(CortexError):
    """Required file, note, or resource not found."""
    pass


class ConfigError(CortexError):
    """Configuration error (missing or invalid config values)."""
    pass


class NotInitializedError(CortexError):
    """Vault not initialized (no root.md found)."""
    pass


class AlreadyExistsError(CortexError):
    """Resource already exists (file, project, etc.)."""
    pass


class SyncError(CortexError):
    """Error during sync/maintenance operations."""
    pass


class ExternalServiceError(CortexError):
    """Error communicating with external service (API call failed)."""
    pass
