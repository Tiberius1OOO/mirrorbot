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
import os
import time

import discord
from discord import app_commands

from commands import context, slash
from helpers.database import (
    get_guild_config,
    get_observed_channel_ids,
    increment_message_counter,
    increment_tracked_user_words,
    init_db,
    migrate_from_json,
)
from helpers.text import count_words, split_message
from helpers.webhooks import get_or_create_webhook

TOKEN = os.getenv("DISCORD_TOKEN_MIRRORBOT")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN_MIRRORBOT environment variable not set.")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Register command modules
slash.register(tree, client)
context.register(tree, client)


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


START_TIME = time.time()
client.run(TOKEN)
