import json
import os
import sqlite3

# Database location
DB_FOLDER = "data"
DB_FILE = os.path.join(DB_FOLDER, "bot.db")

# Old JSON config folder (for migration)
CONFIG_FOLDER = "configs"


def get_connection():
    """
    Returns a SQLite connection to the bot database.
    Ensures the database folder exists.
    """
    os.makedirs(DB_FOLDER, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Initializes the database and creates required tables
    if they do not already exist.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Guild settings
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            error_channel INTEGER
        )
        """
    )

    # Relay configurations
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS relays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            source_channel INTEGER,
            target_channel INTEGER,
            delay INTEGER DEFAULT 0,
            UNIQUE(guild_id, source_channel)
        )
        """
    )

    # Stats table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS stats (
            guild_id INTEGER PRIMARY KEY,
            messages_copied INTEGER DEFAULT 0,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
        )
        """
    )

    # Ensure uniqueness even on older databases
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_relay_unique
        ON relays (guild_id, source_channel)
        """
    )

    conn.commit()
    conn.close()


# =========================================================
# Migration
# =========================================================


def guild_exists(guild_id: int) -> bool:
    """
    Returns True if the guild already exists in the database.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM guilds WHERE guild_id = ?", (guild_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def migrate_from_json():
    """
    Migrates old JSON configs into the SQLite database.

    After successful migration, the JSON file is renamed to:
    <guild_id>.migrated.json

    This runs per guild and skips configs that already
    exist in the database.
    """
    if not os.path.exists(CONFIG_FOLDER):
        return

    conn = get_connection()
    cursor = conn.cursor()

    for filename in os.listdir(CONFIG_FOLDER):
        # Skip non-JSON or already migrated files
        if not filename.endswith(".json") or filename.endswith(".migrated.json"):
            continue

        guild_id = int(filename.replace(".json", ""))
        path = os.path.join(CONFIG_FOLDER, filename)

        # Skip if guild already exists in DB
        if guild_exists(guild_id):
            continue

        with open(path, "r") as f:
            data = json.load(f)

        # Insert guild
        error_channel = data.get("error_channel")
        cursor.execute(
            "INSERT INTO guilds (guild_id, error_channel) VALUES (?, ?)",
            (guild_id, error_channel),
        )

        # Insert stats
        messages_copied = data.get("stats", {}).get("messages_copied", 0)
        cursor.execute(
            "INSERT INTO stats (guild_id, messages_copied) VALUES (?, ?)",
            (guild_id, messages_copied),
        )

        # Insert relays
        for relay in data.get("relays", []):
            cursor.execute(
                """
                INSERT INTO relays
                (guild_id, source_channel, target_channel, delay)
                VALUES (?, ?, ?, ?)
                """,
                (
                    guild_id,
                    relay["source"],
                    relay["target"],
                    relay.get("delay", 0),
                ),
            )

        # Rename JSON after migration
        migrated_path = os.path.join(CONFIG_FOLDER, f"{guild_id}.migrated.json")
        os.rename(path, migrated_path)

    conn.commit()
    conn.close()


# =========================================================
# Config access
# =========================================================


def get_guild_config(guild_id: int):
    """
    Returns the guild configuration in the old JSON-style
    structure so the rest of the bot can use it unchanged.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT error_channel FROM guilds WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    config = {
        "error_channel": row["error_channel"],
        "relays": [],
        "stats": {"messages_copied": 0},
    }

    cursor.execute(
        "SELECT source_channel, target_channel, delay FROM relays WHERE guild_id = ?",
        (guild_id,),
    )
    for r in cursor.fetchall():
        config["relays"].append(
            {
                "source": r["source_channel"],
                "target": r["target_channel"],
                "delay": r["delay"],
            }
        )

    cursor.execute("SELECT messages_copied FROM stats WHERE guild_id = ?", (guild_id,))
    stats_row = cursor.fetchone()
    if stats_row:
        config["stats"]["messages_copied"] = stats_row["messages_copied"]

    conn.close()
    return config


# =========================================================
# Write operations
# =========================================================


def set_error_channel(guild_id: int, channel_id: int):
    """
    Sets or updates the error channel for a guild.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO guilds (guild_id, error_channel)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET error_channel = excluded.error_channel
        """,
        (guild_id, channel_id),
    )

    cursor.execute(
        "INSERT OR IGNORE INTO stats (guild_id, messages_copied) VALUES (?, 0)",
        (guild_id,),
    )

    conn.commit()
    conn.close()


def add_relay(guild_id: int, source: int, target: int, delay: int):
    """
    Adds or replaces a relay for a source channel.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO relays
        (guild_id, source_channel, target_channel, delay)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(guild_id, source_channel)
        DO UPDATE SET
            target_channel = excluded.target_channel,
            delay = excluded.delay
        """,
        (guild_id, source, target, delay),
    )

    conn.commit()
    conn.close()


def remove_relay(guild_id: int, source: int):
    """
    Removes a relay from a source channel.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM relays WHERE guild_id = ? AND source_channel = ?",
        (guild_id, source),
    )

    conn.commit()
    conn.close()


def increment_message_counter(guild_id: int, amount: int = 1):
    """
    Increments the copied message counter for a guild.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO stats (guild_id, messages_copied)
        VALUES (?, ?)
        ON CONFLICT(guild_id)
        DO UPDATE SET messages_copied = messages_copied + ?
        """,
        (guild_id, amount, amount),
    )

    conn.commit()
    conn.close()
