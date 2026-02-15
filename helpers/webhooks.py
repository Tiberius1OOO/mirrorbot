"""
Webhook Utilities
=================

Provides helper functions for managing Discord webhooks
used by the Mirror Bot.

Purpose
-------
Webhooks are used to:

• Preserve the original sender’s username
• Preserve the original avatar
• Avoid the bot appearing as the message author
• Provide cleaner mirrored messages

This module maintains a simple in-memory cache to avoid
recreating or refetching webhooks for the same channel.

Caching Behavior
----------------
• Webhooks are cached per channel ID
• If a webhook already exists, it is reused
• If not, a new webhook named "DragonCopy" is created
• Cache resets when the bot restarts

Limitations
-----------
• Cache is not persistent across restarts
• If a webhook is manually deleted, it will be recreated
"""

import discord

webhook_cache = {}


async def get_or_create_webhook(channel: discord.TextChannel):
    """
    Returns a webhook for the given channel.

    Behavior:
    • Checks the in-memory cache first
    • If not cached, searches existing webhooks
    • If none named "DragonCopy" exist, creates one
    • Stores the result in the cache

    Args:
        channel (discord.TextChannel):
            The target channel where the webhook should send messages.

    Returns:
        discord.Webhook:
            The existing or newly created webhook.
    """
    if channel.id in webhook_cache:
        return webhook_cache[channel.id]

    webhooks = await channel.webhooks()
    for hook in webhooks:
        if hook.name == "DragonCopy":
            webhook_cache[channel.id] = hook
            return hook

    hook = await channel.create_webhook(name="DragonCopy")
    webhook_cache[channel.id] = hook
    return hook
