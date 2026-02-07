"""Vault configuration and path resolution.

This module reads and writes a YAML config at ~/.config/cortex/config.yaml
to store the active vault and other user preferences. 
"""

import os
from pathlib import Path

import yaml


def _config_dir() -> Path:
    """Return the configuration directory (respects XDG_CONFIG_HOME)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "cortex"


def _config_file() -> Path:
    """Return the path to the config file."""
    return _config_dir() / "config.yaml"


def load_config() -> dict:
    """Load config from the config file, returning an empty dict if missing."""
    cfg = _config_file()
    if not cfg.exists():
        return {}
    try:
        return yaml.safe_load(cfg.read_text()) or {}
    except yaml.YAMLError:
        return {}


def save_config(config: dict) -> None:
    """Save config to the config file, creating directories as needed."""
    cfg_dir = _config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    _config_file().write_text(yaml.dump(config, default_flow_style=False))


def get_vault_path() -> Path:
    """Get vault path from config file.

    Raises ValueError if not configured.
    """
    config = load_config()
    if "vault" not in config or not config["vault"]:
        raise ValueError(
            "Vault path not configured. Run 'cor config set vault /path/to/notes' first."
        )
    return Path(config["vault"])


def set_vault_path(path: Path) -> None:
    """Save vault path to config file."""
    config = load_config()
    config["vault"] = str(path.resolve())
    save_config(config)


def is_vault_initialized(vault_path: Path | None = None) -> bool:
    """Check if a vault is initialized (has root.md)."""
    vault = vault_path or get_vault_path()
    return (vault / "root.md").exists()


def get_verbosity() -> int:
    """Get verbosity level from config (default: 1)."""
    config = load_config()
    return config.get("verbosity", 1)


def set_verbosity(level: int) -> None:
    """Save verbosity level to config file (0-3)."""
    if not 0 <= level <= 3:
        raise ValueError("Verbosity level must be between 0 and 3")
    config = load_config()
    config["verbosity"] = level
    save_config(config)


def config_file() -> Path:
    """Return the current config file path."""
    return _config_file()


def get_remote_inbox() -> str | None:
    """Get Telegram bot token for remote inbox.

    Returns token from config file or TELEGRAM_BOT_TOKEN env var, or None if not configured.
    """
    # Check environment variable first
    env_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if env_token:
        return env_token

    # Fall back to config file
    config = load_config()
    return config.get("remote_inbox")


def set_remote_inbox(bot_token: str) -> None:
    """Save Telegram bot token to config file."""
    config = load_config()
    config["remote_inbox"] = bot_token
    save_config(config)


def get_focused_project() -> str | None:
    """Get the currently focused project from config.
    
    Returns project name or None if no focus set.
    """
    config = load_config()
    return config.get("focused_project")


def set_focused_project(project: str) -> None:
    """Set the focused project in config."""
    config = load_config()
    config["focused_project"] = project
    save_config(config)


def clear_focused_project() -> None:
    """Clear the focused project from config."""
    config = load_config()
    if "focused_project" in config:
        del config["focused_project"]
        save_config(config)
