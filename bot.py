"""
DragonCopy Mirror Bot
=====================

Main entry point for the Discord Mirror Bot.

This module initializes the Discord client, loads command modules,
and handles live message relays between channels.

Overview
--------
The bot provides tools for:

• Copying messages between channels
• Relaying messages live with optional delay
• Preserving usernames and avatars using webhooks
• Per-server configuration stored as JSON
• Administrator-only control commands

Architecture
------------
The bot is split into logical modules:

helpers/
    config.py     → configuration loading and saving
    text.py       → message splitting utilities
    webhooks.py   → webhook creation and caching

commands/
    slash.py      → slash commands (/setup, /start_relay, etc.)
    context.py    → right-click message commands

bot.py
    Main runtime:
    • Initializes Discord client
    • Registers command modules
    • Handles live relay logic
    • Starts the bot

Environment Variables
---------------------
DISCORD_TOKEN
    Required. The Discord bot token used for authentication.

Example (Linux/macOS):
    export DISCORD_TOKEN="your_token_here"

Example (systemd service):
    Environment=DISCORD_TOKEN=your_token_here

Relay Behavior
--------------
When a message is sent in a configured source channel:

1. Bot checks active relay configurations
2. If a match is found:
   • Waits for the configured delay
   • Splits long messages into ≤2000 characters
   • Reposts using a webhook
   • Preserves username and avatar

Limitations
-----------
• Pending delayed messages are lost if the bot restarts
• Large channel copies are slow due to Discord rate limits
• No database is used; all data is stored in JSON files

Author
------
DragonCopy project – designed for collaborative writing and RP servers.
"""

import asyncio
import os

import discord
from discord import app_commands

from commands import context, slash
from helpers.config import load_and_prepare_config, save_config
from helpers.text import split_message
from helpers.webhooks import get_or_create_webhook

TOKEN = os.getenv("DISCORD_TOKEN_MIRRORBOT")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN environment variable not set.")

config_locks = {}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def get_guild_lock(guild_id: int):
    if guild_id not in config_locks:
        config_locks[guild_id] = asyncio.Lock()
    return config_locks[guild_id]


# Register commands
slash.register(tree, client)
context.register(tree, client)


@client.event
async def on_message(message: discord.Message):
    """
    Handles incoming messages and forwards them via relay
    if a matching relay configuration exists.

    Behavior:
    • Ignores bot messages
    • Ignores messages outside guilds
    • Checks configured relays for the guild
    • If a relay matches:
        - waits for the configured delay
        - splits long messages
        - sends via webhook
        - preserves username and avatar
    """
    if message.author.bot:
        return

    guild = message.guild
    if not guild:
        return

    config = load_and_prepare_config(guild.id)
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

                # optional stat update
                lock = get_guild_lock(guild.id)
                async with lock:
                    config = load_and_prepare_config(guild.id)
                    if config:
                        stats = config.setdefault("stats", {})
                        stats["messages_copied"] = stats.get("messages_copied", 0) + 1
                        save_config(guild.id, config)

            except Exception as e:
                print(f"[ERROR] Relay error: {e}")

        asyncio.create_task(delayed_send(message, target_channel, delay))


@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")
    await tree.sync()
    print("Slash commands synced.")


client.run(TOKEN)
