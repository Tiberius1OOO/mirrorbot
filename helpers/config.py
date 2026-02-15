"""
Configuration Utilities
=======================

Handles per-server configuration storage and validation.

Primary responsibilities:
• Loading guild configuration files
• Ensuring required keys exist
• Saving updated configuration data

Design Philosophy
-----------------
Each Discord server (guild) gets its own JSON configuration file.
This keeps data isolated between communities and avoids the need
for a database.

Configuration files are stored in:

    configs/<guild_id>.json

Automatic Repair
----------------
When a config is loaded, this module verifies that required
fields exist. If something is missing, it is added automatically
and the file is updated on disk.

This prevents crashes caused by:
• Old config versions
• Manual edits
• Missing keys
"""

import json
import os

CONFIG_FOLDER = "configs"


def get_config_path(guild_id: int):
    """
    Returns the file path for a guild's configuration.

    Args:
        guild_id (int):
            Discord guild ID.

    Returns:
        str:
            Path to the config file.
    """
    return os.path.join(CONFIG_FOLDER, f"{guild_id}.json")


def save_config(guild_id: int, data: dict):
    """
    Saves the configuration data for a guild.

    Creates the config folder if it does not exist.

    Args:
        guild_id (int):
            Discord guild ID.

        data (dict):
            Configuration data to save.
    """
    os.makedirs(CONFIG_FOLDER, exist_ok=True)
    with open(get_config_path(guild_id), "w") as f:
        json.dump(data, f, indent=4)


def load_and_prepare_config(guild_id: int):
    """
    Loads a guild's configuration and ensures
    required fields exist.

    Missing keys are added automatically and
    saved back to disk.

    Required structure:
        {
            "error_channel": int,
            "relays": list,
            "stats": {
                "messages_copied": int
            }
        }

    Args:
        guild_id (int):
            Discord guild ID.

    Returns:
        dict | None:
            Prepared configuration dictionary,
            or None if no config exists.
    """
    path = get_config_path(guild_id)

    if not os.path.exists(path):
        return None

    with open(path, "r") as f:
        config = json.load(f)

    changed = False

    if "relays" not in config:
        config["relays"] = []
        changed = True

    if "stats" not in config:
        config["stats"] = {"messages_copied": 0}
        changed = True

    if "messages_copied" not in config["stats"]:
        config["stats"]["messages_copied"] = 0
        changed = True

    if changed:
        save_config(guild_id, config)

    return config
