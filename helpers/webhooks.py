import discord

webhook_cache = {}


async def get_or_create_webhook(channel: discord.TextChannel):
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
