import json
import os
import sqlite3
from typing import Optional

# Database location
DB_FOLDER = "data"
DB_FILE = os.path.join(DB_FOLDER, "bot.db")

# guild_id -> frozenset of observed channel/thread ids (invalidated on observe changes)
_observed_channel_cache: dict[int, frozenset[int]] = {}

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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            error_channel INTEGER
        )
        """)

    # Relay configurations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            source_channel INTEGER,
            target_channel INTEGER,
            delay INTEGER DEFAULT 0,
            UNIQUE(guild_id, source_channel)
        )
        """)

    # Stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            guild_id INTEGER PRIMARY KEY,
            messages_copied INTEGER DEFAULT 0,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
        )
        """)

    # Per-user word totals from *observed* channels/threads (see /observe)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relay_word_stats (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            word_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS observed_channels (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, channel_id)
        )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_word_watermarks (
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            up_to_message_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, channel_id)
        )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ranking_autopost (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER,
            interval_hours INTEGER NOT NULL DEFAULT 24
                CHECK (interval_hours IN (12, 24)),
            post_hour_utc INTEGER NOT NULL DEFAULT 12
                CHECK (post_hour_utc BETWEEN 0 AND 23),
            post_minute_utc INTEGER NOT NULL DEFAULT 0
                CHECK (post_minute_utc BETWEEN 0 AND 59),
            last_fired_slot TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 0
        )
        """)

    # Ensure uniqueness even on older databases
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_relay_unique
        ON relays (guild_id, source_channel)
        """)

    conn.commit()
    conn.close()

    invalidate_observed_cache()


# =========================================================
# Observed channels (word tracking)
# =========================================================


def invalidate_observed_cache(guild_id: Optional[int] = None) -> None:
    if guild_id is None:
        _observed_channel_cache.clear()
    else:
        _observed_channel_cache.pop(guild_id, None)


def get_observed_channel_ids(guild_id: int) -> frozenset[int]:
    if guild_id not in _observed_channel_cache:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT channel_id FROM observed_channels WHERE guild_id = ?",
            (guild_id,),
        )
        _observed_channel_cache[guild_id] = frozenset(
            int(r["channel_id"]) for r in cursor.fetchall()
        )
        conn.close()
    return _observed_channel_cache[guild_id]


def is_channel_observed(guild_id: int, channel_id: int) -> bool:
    return channel_id in get_observed_channel_ids(guild_id)


def add_observed_channel(guild_id: int, channel_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO observed_channels (guild_id, channel_id)
        VALUES (?, ?)
        """,
        (guild_id, channel_id),
    )
    conn.commit()
    conn.close()
    invalidate_observed_cache(guild_id)


def remove_observed_channel(guild_id: int, channel_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM observed_channels WHERE guild_id = ? AND channel_id = ?",
        (guild_id, channel_id),
    )
    conn.commit()
    conn.close()
    invalidate_observed_cache(guild_id)


def list_observed_channels(guild_id: int) -> list[int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT channel_id FROM observed_channels WHERE guild_id = ? ORDER BY channel_id",
        (guild_id,),
    )
    ids = [int(r["channel_id"]) for r in cursor.fetchall()]
    conn.close()
    return ids


def get_watermark(guild_id: int, channel_id: int) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT up_to_message_id FROM channel_word_watermarks
        WHERE guild_id = ? AND channel_id = ?
        """,
        (guild_id, channel_id),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return int(row["up_to_message_id"])


def set_watermark(guild_id: int, channel_id: int, up_to_message_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO channel_word_watermarks (guild_id, channel_id, up_to_message_id)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, channel_id)
        DO UPDATE SET up_to_message_id = excluded.up_to_message_id
        """,
        (guild_id, channel_id, up_to_message_id),
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


def apply_user_word_deltas(guild_id: int, deltas: dict[int, int]) -> None:
    """Apply many user word increments in one transaction."""
    if not deltas:
        return
    conn = get_connection()
    cursor = conn.cursor()
    for user_id, words in deltas.items():
        if words <= 0:
            continue
        cursor.execute(
            """
            INSERT INTO relay_word_stats (guild_id, user_id, word_count)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET word_count = word_count + excluded.word_count
            """,
            (guild_id, user_id, words),
        )
    conn.commit()
    conn.close()


def increment_tracked_user_words(guild_id: int, user_id: int, words: int) -> None:
    """Adds words for one user (live message in an observed channel)."""
    if words <= 0:
        return
    apply_user_word_deltas(guild_id, {user_id: words})


def get_total_tracked_words(guild_id: int) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(word_count), 0) AS t FROM relay_word_stats WHERE guild_id = ?",
        (guild_id,),
    )
    total = int(cursor.fetchone()["t"])
    conn.close()
    return total


def get_total_relay_source_words(guild_id: int) -> int:
    """Backward-compatible alias for totals used in /bot_info."""
    return get_total_tracked_words(guild_id)


def get_tracked_writer_count(guild_id: int) -> int:
    """Members with at least one counted word in observed channels."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS c FROM relay_word_stats
        WHERE guild_id = ? AND word_count > 0
        """,
        (guild_id,),
    )
    c = int(cursor.fetchone()["c"])
    conn.close()
    return c


def get_relay_writer_count(guild_id: int) -> int:
    """Alias for older name."""
    return get_tracked_writer_count(guild_id)


def get_user_tracked_word_rank(
    guild_id: int, user_id: int
) -> tuple[int, Optional[int], int]:
    """
    Returns (words, rank, writers_with_words).
    rank is 1-based; None if words == 0 (not on leaderboard).
    writers_with_words counts users with word_count > 0.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) AS c FROM relay_word_stats
        WHERE guild_id = ? AND word_count > 0
        """,
        (guild_id,),
    )
    writers_with_words = int(cursor.fetchone()["c"])

    cursor.execute(
        "SELECT word_count FROM relay_word_stats WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    row = cursor.fetchone()
    words = int(row["word_count"]) if row else 0

    if words <= 0:
        conn.close()
        return words, None, writers_with_words

    cursor.execute(
        """
        SELECT COUNT(*) + 1 AS rnk FROM relay_word_stats
        WHERE guild_id = ? AND word_count > ?
        """,
        (guild_id, words),
    )
    rank = int(cursor.fetchone()["rnk"])
    conn.close()
    return words, rank, writers_with_words


def get_user_relay_word_rank(
    guild_id: int, user_id: int
) -> tuple[int, Optional[int], int]:
    """Alias for /bot_info."""
    return get_user_tracked_word_rank(guild_id, user_id)


def get_top_tracked_writers(guild_id: int, limit: int = 10) -> list[tuple[int, int]]:
    """List of (user_id, word_count) descending."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, word_count FROM relay_word_stats
        WHERE guild_id = ? AND word_count > 0
        ORDER BY word_count DESC, user_id ASC
        LIMIT ?
        """,
        (guild_id, limit),
    )
    rows = [(int(r["user_id"]), int(r["word_count"])) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_top_relay_writers(guild_id: int, limit: int = 10) -> list[tuple[int, int]]:
    return get_top_tracked_writers(guild_id, limit)


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


# =========================================================
# Ranking autopost (/ranking_setup)
# =========================================================


def get_ranking_autopost(guild_id: int) -> Optional[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT guild_id, channel_id, interval_hours, post_hour_utc,
               post_minute_utc, last_fired_slot, enabled
        FROM ranking_autopost WHERE guild_id = ?
        """,
        (guild_id,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "guild_id": int(row["guild_id"]),
        "channel_id": int(row["channel_id"]) if row["channel_id"] is not None else None,
        "interval_hours": int(row["interval_hours"]),
        "post_hour_utc": int(row["post_hour_utc"]),
        "post_minute_utc": int(row["post_minute_utc"]),
        "last_fired_slot": str(row["last_fired_slot"] or ""),
        "enabled": bool(row["enabled"]),
    }


def save_ranking_autopost(
    guild_id: int,
    channel_id: int,
    interval_hours: int,
    post_hour_utc: int,
    post_minute_utc: int,
    enabled: bool = True,
) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ranking_autopost (
            guild_id, channel_id, interval_hours,
            post_hour_utc, post_minute_utc, last_fired_slot, enabled
        )
        VALUES (?, ?, ?, ?, ?, '', ?)
        ON CONFLICT(guild_id) DO UPDATE SET
            channel_id = excluded.channel_id,
            interval_hours = excluded.interval_hours,
            post_hour_utc = excluded.post_hour_utc,
            post_minute_utc = excluded.post_minute_utc,
            enabled = excluded.enabled,
            last_fired_slot = ''
        """,
        (
            guild_id,
            channel_id,
            interval_hours,
            post_hour_utc,
            post_minute_utc,
            1 if enabled else 0,
        ),
    )
    conn.commit()
    conn.close()


def disable_ranking_autopost(guild_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ranking_autopost (
            guild_id, channel_id, interval_hours,
            post_hour_utc, post_minute_utc, last_fired_slot, enabled
        )
        VALUES (?, NULL, 24, 12, 0, '', 0)
        ON CONFLICT(guild_id) DO UPDATE SET enabled = 0
        """,
        (guild_id,),
    )
    conn.commit()
    conn.close()


def set_ranking_last_fired_slot(guild_id: int, slot_key: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE ranking_autopost SET last_fired_slot = ?
        WHERE guild_id = ?
        """,
        (slot_key, guild_id),
    )
    conn.commit()
    conn.close()


def iter_active_ranking_autopost() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT guild_id, channel_id, interval_hours, post_hour_utc,
               post_minute_utc, last_fired_slot, enabled
        FROM ranking_autopost
        WHERE enabled = 1 AND channel_id IS NOT NULL
        """
    )
    rows = []
    for row in cursor.fetchall():
        rows.append(
            {
                "guild_id": int(row["guild_id"]),
                "channel_id": int(row["channel_id"]),
                "interval_hours": int(row["interval_hours"]),
                "post_hour_utc": int(row["post_hour_utc"]),
                "post_minute_utc": int(row["post_minute_utc"]),
                "last_fired_slot": str(row["last_fired_slot"] or ""),
                "enabled": bool(row["enabled"]),
            }
        )
    conn.close()
    return rows
