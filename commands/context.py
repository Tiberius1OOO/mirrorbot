"""
Context Menu Commands
=====================

Registers right-click message context actions for the bot.
"""

import asyncio

import discord
from discord import app_commands

from helpers.database import increment_message_counter
from helpers.text import split_message
from helpers.webhooks import get_or_create_webhook


def register(tree, client):
    """
    Registers context menu commands with the bot.
    """

    @tree.context_menu(name="Copy message")
    @app_commands.checks.has_permissions(administrator=True)
    async def copy_message_context(
        interaction: discord.Interaction, message: discord.Message
    ):
        """
        Opens a channel selector to copy a message
        into another channel.
        """
        view = CopyView(message)
        await interaction.response.send_message(
            "Select target channel:", view=view, ephemeral=True
        )


class CopyChannelSelect(discord.ui.ChannelSelect):
    """
    Channel selection UI component for message copying.
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
        Handles the channel selection event and copies the message.
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

            # Increment stats counter
            increment_message_counter(guild.id, 1)

            await interaction.response.send_message("Message copied.", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)


class CopyView(discord.ui.View):
    """
    UI container for the message copy interface.
    """

    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(CopyChannelSelect(message))
