"""
Backfill word counts when an admin starts observing a channel or thread.
"""

import asyncio

import discord

from helpers.database import apply_user_word_deltas, get_watermark, set_watermark
from helpers.text import count_words


def _should_count_message(message: discord.Message) -> bool:
    """Match EPUB export: skip real bot posts, keep webhook-mirrored posts."""
    if message.author.bot and not message.webhook_id:
        return False
    return True


async def backfill_observed_channel(
    guild_id: int, channel: discord.TextChannel | discord.Thread
) -> tuple[int, dict[int, int]]:
    """
    Scan channel history and add word deltas per user. Uses a watermark so
    re-observing after /unobserve only counts new messages.

    Returns (messages_iterated, user_id -> words added this run).
    """
    watermark = get_watermark(guild_id, channel.id)
    per_user: dict[int, int] = {}
    max_id = watermark or 0
    n = 0

    kwargs: dict = {"limit": None, "oldest_first": True}
    if watermark is not None:
        kwargs["after"] = discord.Object(id=watermark)

    async for msg in channel.history(**kwargs):
        n += 1
        if not _should_count_message(msg):
            continue
        w = count_words(msg.content or "")
        if w:
            uid = msg.author.id
            per_user[uid] = per_user.get(uid, 0) + w
        if msg.id > max_id:
            max_id = msg.id
        if n % 400 == 0:
            await asyncio.sleep(0)

    apply_user_word_deltas(guild_id, per_user)

    last = channel.last_message_id
    if last is not None and last > max_id:
        max_id = last
    if max_id > 0:
        set_watermark(guild_id, channel.id, max_id)

    return n, per_user
