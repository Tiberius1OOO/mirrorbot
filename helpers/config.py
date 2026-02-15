import json
import os

CONFIG_FOLDER = "configs"


def get_config_path(guild_id: int):
    return os.path.join(CONFIG_FOLDER, f"{guild_id}.json")


def save_config(guild_id: int, data: dict):
    os.makedirs(CONFIG_FOLDER, exist_ok=True)
    with open(get_config_path(guild_id), "w") as f:
        json.dump(data, f, indent=4)


def load_and_prepare_config(guild_id: int):
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
