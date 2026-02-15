"""
Context Menu Commands
=====================

Registers right-click message context actions for the bot.

Primary responsibilities:
• Message-level actions via Discord's context menu
• Manual copying of individual messages
• Channel selection interface for copy targets

Architecture
------------
Context commands are registered through a `register`
function, similar to slash commands. This keeps all
right-click logic isolated from the main bot file.

User Flow
---------
1. Administrator right-clicks a message.
2. Selects "Apps → Copy message".
3. Chooses a destination channel.
4. Bot copies the message using a webhook.

Features
--------
• Preserves username and avatar
• Supports attachments
• Automatically splits long messages
"""

import asyncio

import discord
from discord import app_commands

from helpers.text import split_message
from helpers.webhooks import get_or_create_webhook


def register(tree, client):
    """
    Registers context menu commands with the bot.

    Args:
        tree (app_commands.CommandTree):
            The bot's command tree.

        client (discord.Client):
            The main Discord client instance.
    """

    @tree.context_menu(name="Copy message")
    @app_commands.checks.has_permissions(administrator=True)
    async def copy_message_context(
        interaction: discord.Interaction, message: discord.Message
    ):
        """
        Opens a channel selector to copy a message
        into another channel.

        The copied message preserves:
        • Username
        • Avatar
        • Attachments
        • Content formatting

        Long messages are automatically split to
        respect Discord's character limits.

        Admin only.
        """
        view = CopyView(message)
        await interaction.response.send_message(
            "Select target channel:", view=view, ephemeral=True
        )


class CopyChannelSelect(discord.ui.ChannelSelect):
    """
    Channel selection UI component for message copying.

    Allows an administrator to choose the destination
    channel where the selected message will be copied.

    Stores the original message and performs the copy
    once a channel is selected.
    """

    def __init__(self, message: discord.Message):
        super().__init__(
            placeholder="Select target channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.source_message = message

    async def callback(self, interaction: discord.Interaction):
        """
        Handles the channel selection event.

        Copies the stored source message into the
        selected channel using a webhook.

        Features:
        • Preserves author identity
        • Supports attachments
        • Splits long messages safely
        """
        selected_channel = self.values[0]
        guild = interaction.guild
        target_channel = guild.get_channel(selected_channel.id)

        try:
            webhook = await get_or_create_webhook(target_channel)

            username = self.source_message.author.display_name
            avatar = self.source_message.author.display_avatar.url
            content = self.source_message.content or ""

            files = []
            for attachment in self.source_message.attachments:
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

            await interaction.response.send_message("Message copied.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)


class CopyView(discord.ui.View):
    """
    UI container for the message copy interface.

    Holds the channel selection component and
    manages the interaction timeout.
    """

    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(CopyChannelSelect(message))
