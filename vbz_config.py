"""Configuration persistence for VBZBreaker.

Saves and restores training parameters between application launches.
"""
import json
import os
import sys
from typing import Dict, Any


def get_config_path() -> str:
    """Get platform-appropriate config file path.

    Returns:
        Path to the config file based on the platform.
    """
    if sys.platform == 'win32':
        # Windows: Use AppData\Local
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        config_dir = os.path.join(base, 'VBZBreaker')
    elif sys.platform == 'darwin':
        # macOS: Use ~/Library/Application Support
        config_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'VBZBreaker')
    else:
        # Linux/Unix: Use XDG_CONFIG_HOME or ~/.config
        xdg_config = os.environ.get('XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config'))
        config_dir = os.path.join(xdg_config, 'vbzbreaker')

    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'config.json')


def load_config() -> Dict[str, Any]:
    """Load configuration from disk.

    Returns:
        Dictionary with configuration data, or empty dict if file doesn't exist.
    """
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # If config is corrupted, return empty dict
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to disk.

    Args:
        config: Dictionary with configuration data to save.
    """
    config_path = get_config_path()
    try:
        with open(config_path, 'w') as f:
            json.dump(config, indent=2, fp=f)
    except IOError:
        # Silently fail if we can't write config
        pass
