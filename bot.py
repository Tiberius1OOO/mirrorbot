"""
DragonCopy Mirror Bot
=====================

Main entry point for the Discord Mirror Bot.

Handles:
• Discord client setup
• Command registration
• Live relay processing
• Database initialization and migration
"""

import subprocess
import sys
from pathlib import Path


def _ensure_dependencies():
    """
    If core third-party packages are missing (e.g. after pulling a newer
    release without running pip), install from requirements.txt once.
    """
    root = Path(__file__).resolve().parent
    req = root / "requirements.txt"
    if not req.is_file():
        return

    def _imports_ok():
        try:
            import discord  # noqa: F401
            import ebooklib  # noqa: F401
            import aiohttp  # noqa: F401
            return True
        except ImportError:
            return False

    if _imports_ok():
        return

    print("[DragonCopy] Missing packages; installing from requirements.txt ...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(req)],
            cwd=str(root),
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            "Failed to install dependencies with pip. "
            "Install manually: pip install -r requirements.txt"
        ) from e

    if not _imports_ok():
        raise RuntimeError(
            "Dependencies still missing after pip install. "
            "Restart the bot or run: pip install -r requirements.txt"
        )

    print("[DragonCopy] Dependencies installed successfully.")


_ensure_dependencies()

import asyncio
import logging
import os
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import tasks

from commands import context, slash
from helpers.app_command_errors import respond_app_command_permission_denied
from helpers.database import (
    get_guild_config,
    get_observed_channel_ids,
    get_top_relay_writers,
    increment_message_counter,
    increment_tracked_user_words,
    init_db,
    iter_active_ranking_autopost,
    migrate_from_json,
    set_ranking_last_fired_slot,
)
from helpers.ranking_autopost import ranking_should_fire, ranking_slot_key_utc
from helpers.ranking_display import post_ranking_to_channel
from helpers.text import count_words, split_message
from helpers.webhooks import get_or_create_webhook

_log = logging.getLogger(__name__)

TOKEN = os.getenv("DISCORD_TOKEN_MIRRORBOT")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN_MIRRORBOT environment variable not set.")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class DragonCopyClient(discord.Client):
    """Client with ``start_time`` set in ``on_ready`` (used by /bot_info uptime)."""

    start_time: float

    def __init__(self, *, intents: discord.Intents) -> None:
        super().__init__(intents=intents)
        self.start_time = 0.0


client = DragonCopyClient(intents=intents)
tree = app_commands.CommandTree(client)

# Register command modules
slash.register(tree, client)
context.register(tree, client)


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if await respond_app_command_permission_denied(interaction, error):
        return
    cmd = interaction.command
    if cmd is not None and not cmd._has_any_error_handlers():
        _log.error("Ignoring exception in command %r", cmd.name, exc_info=error)


@tasks.loop(minutes=1.0)
async def ranking_autopost_loop():
    now = datetime.now(timezone.utc)
    for row in iter_active_ranking_autopost():
        if not ranking_should_fire(
            row["interval_hours"],
            row["post_hour_utc"],
            row["post_minute_utc"],
            row["last_fired_slot"],
            now,
        ):
            continue
        guild = client.get_guild(row["guild_id"])
        if guild is None:
            continue
        ch = guild.get_channel_or_thread(row["channel_id"])
        if ch is None:
            try:
                ch = await client.fetch_channel(row["channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        if not isinstance(ch, (discord.TextChannel, discord.Thread)):
            continue
        try:
            entries = get_top_relay_writers(row["guild_id"], 10)
            await post_ranking_to_channel(client, ch, guild, entries)
        except Exception as e:
            print(f"[WARN] ranking_autopost guild={row['guild_id']}: {e}")
        else:
            set_ranking_last_fired_slot(row["guild_id"], ranking_slot_key_utc(now))


@ranking_autopost_loop.before_loop
async def before_ranking_autopost_loop():
    await client.wait_until_ready()


@client.event
async def on_message(message: discord.Message):
    """
    Handles incoming messages and forwards them via relay
    if a matching relay configuration exists.
    """
    guild = message.guild
    if not guild:
        return

    # Word stats: only for /observe channels (webhook posts count like EPUB export)
    skip_for_word_stats = message.author.bot and not message.webhook_id
    if not skip_for_word_stats:
        if message.channel.id in get_observed_channel_ids(guild.id):
            wc = count_words(message.content or "")
            if wc:
                increment_tracked_user_words(guild.id, message.author.id, wc)

    if message.author.bot:
        return

    config = get_guild_config(guild.id)
    if not config:
        return

    relays = config.get("relays", [])

    for relay in relays:
        if message.channel.id != relay["source"]:
            continue

        target_channel = guild.get_channel(relay["target"])
        if not target_channel:
            continue

        delay = relay["delay"]

        async def delayed_send(msg, target, delay_seconds):
            await asyncio.sleep(delay_seconds)

            try:
                webhook = await get_or_create_webhook(target)

                username = msg.author.display_name
                avatar = msg.author.display_avatar.url
                content = msg.content or ""

                files = []
                for attachment in msg.attachments:
                    file = await attachment.to_file()
                    files.append(file)

                if not content and not files:
                    return

                parts = split_message(content) if content else [""]

                for i, part in enumerate(parts):
                    if i == 0 and files:
                        await webhook.send(
                            content=part,
                            username=username,
                            avatar_url=avatar,
                            files=files,
                        )
                    else:
                        await webhook.send(
                            content=part,
                            username=username,
                            avatar_url=avatar,
                        )

                    await asyncio.sleep(1.0)

                # Update stats in DB
                increment_message_counter(guild.id, 1)

            except Exception as e:
                print(f"[ERROR] Relay error: {e}")

        asyncio.create_task(delayed_send(message, target_channel, delay))


@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")

    # Initialize DB and migrate JSON
    init_db()
    migrate_from_json()

    await tree.sync()
    print("Slash commands synced.")
    print("Database ready.")
    client.start_time = START_TIME
    if not ranking_autopost_loop.is_running():
        ranking_autopost_loop.start()


START_TIME = time.time()
client.run(TOKEN)
