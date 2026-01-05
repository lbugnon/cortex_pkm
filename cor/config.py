"""Vault configuration and path resolution."""

import os
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".config" / "cortex"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def load_config() -> dict:
    """Load config from ~/.config/cortex/config.yaml."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return yaml.safe_load(CONFIG_FILE.read_text()) or {}
    except yaml.YAMLError:
        return {}


def save_config(config: dict) -> None:
    """Save config to ~/.config/cortex/config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(yaml.dump(config, default_flow_style=False))


def get_vault_path() -> Path:
    """Get vault path with resolution priority.

    Priority:
    1. CORTEX_VAULT environment variable
    2. Config file (~/.config/cortex/config.yaml)
    3. Current directory (fallback)
    """
    # 1. Environment variable
    env_vault = os.environ.get("CORTEX_VAULT")
    if env_vault:
        return Path(env_vault)

    # 2. Config file
    config = load_config()
    if "vault" in config and config["vault"]:
        return Path(config["vault"])

    # 3. Current directory
    return Path.cwd()


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
    """Get verbosity level from config (default: 0).

    Levels:
    - 0: Silent (only errors and essential output)
    - 1: Normal (standard output)
    - 2: Verbose (detailed information)
    - 3: Debug (very detailed with internals)
    """
    config = load_config()
    return config.get("verbosity", 1)


def set_verbosity(level: int) -> None:
    """Save verbosity level to config file (0-3)."""
    if not 0 <= level <= 3:
        raise ValueError("Verbosity level must be between 0 and 3")
    config = load_config()
    config["verbosity"] = level
    save_config(config)
