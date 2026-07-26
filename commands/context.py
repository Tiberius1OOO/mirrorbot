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

    @tree.context_menu(name="Copy everything from here")
    @app_commands.checks.has_permissions(administrator=True)
    async def copy_from_here_context(
        interaction: discord.Interaction, message: discord.Message
    ):
        view = CopyFromHereView(message)
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Select target channel for copy operation:",
            view=view,
            ephemeral=True,
        )

    @tree.context_menu(name="Cut everything from here")
    @app_commands.checks.has_permissions(administrator=True)
    async def cut_from_here_context(
        interaction: discord.Interaction, message: discord.Message
    ):
        view = CutView(message)
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Select target channel for cut operation:",
            view=view,
            ephemeral=True,
        )


async def _fetch_messages_from_here(source_message: discord.Message):
    """
    Returns the selected message plus every newer message in its channel,
    oldest first.
    """
    messages = []
    source_channel = source_message.channel

    async for msg in source_channel.history(
        after=source_message,
        oldest_first=True,
        limit=None,
    ):
        messages.append(msg)

    messages.insert(0, source_message)
    return messages


async def _copy_message_via_webhook(
    webhook: discord.Webhook,
    message: discord.Message,
) -> bool:
    """
    Copies one message through a webhook.

    Returns True if anything was sent, False if the message had nothing
    Discord can accept (no text and no attachments).
    """
    username = message.author.display_name
    avatar = message.author.display_avatar.url
    content = message.content or ""

    files = []
    for attachment in message.attachments:
        files.append(await attachment.to_file())

    if not content and not files:
        return False

    parts = [part for part in split_message(content) if part] if content else []
    if not parts and not files:
        return False
    if not parts:
        parts = [""]

    for i, part in enumerate(parts):
        if i == 0 and files:
            await webhook.send(
                content=part or None,
                username=username,
                avatar_url=avatar,
                files=files,
            )
        elif part:
            await webhook.send(
                content=part,
                username=username,
                avatar_url=avatar,
            )

    return True


async def _copy_range_to_channel(
    source_message: discord.Message,
    target_channel: discord.abc.GuildChannel,
) -> tuple[list[discord.Message], int]:
    """
    Copies the selected message and all newer messages to target_channel.

    Returns (source_messages, copied_count).
    """
    webhook = await get_or_create_webhook(target_channel)
    messages = await _fetch_messages_from_here(source_message)
    copied = 0

    for msg in messages:
        if await _copy_message_via_webhook(webhook, msg):
            copied += 1
        await asyncio.sleep(1.0)

    return messages, copied


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
                await interaction.response.send_message(
                    "Nothing to copy (empty message).",
                    ephemeral=True,
                )
                return

            parts = split_message(content) if content else [""]
            parts = [part for part in parts if part] or ([""] if files else [])
            if not parts:
                await interaction.response.send_message(
                    "Nothing to copy (empty message).",
                    ephemeral=True,
                )
                return

            for i, part in enumerate(parts):
                if i == 0 and files:
                    await webhook.send(
                        content=part or None,
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
            if interaction.response.is_done():
                await interaction.followup.send(f"Error: {e}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error: {e}", ephemeral=True)


class CopyFromHereChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, message: discord.Message):
        super().__init__(
            placeholder="Select target channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.source_message = message

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]
        guild = interaction.guild
        source_channel = self.source_message.channel
        target_channel = guild.get_channel(selected_channel.id)

        if not target_channel:
            await interaction.response.send_message(
                "Target channel not found.",
                ephemeral=True,
            )
            return

        if target_channel.id == source_channel.id:
            await interaction.response.send_message(
                "Choose a different channel; copying into the same channel is not allowed.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        if self.view is not None:
            self.view.stop()

        try:
            messages, copied = await _copy_range_to_channel(
                self.source_message,
                target_channel,
            )

            if copied:
                increment_message_counter(guild.id, copied)

            await interaction.followup.send(
                f"Copy operation completed. {copied} of {len(messages)} messages copied.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "Missing permissions (Manage Webhooks / Send Messages required).",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"Error during copy operation: {e}",
                ephemeral=True,
            )


class CutChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, message: discord.Message):
        super().__init__(
            placeholder="Select target channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.source_message = message

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]
        guild = interaction.guild
        source_channel = self.source_message.channel
        target_channel = guild.get_channel(selected_channel.id)

        if not target_channel:
            await interaction.response.send_message(
                "Target channel not found.",
                ephemeral=True,
            )
            return

        if target_channel.id == source_channel.id:
            await interaction.response.send_message(
                "Choose a different channel; cutting into the same channel is not allowed.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        if self.view is not None:
            self.view.stop()

        try:
            messages, copied = await _copy_range_to_channel(
                self.source_message,
                target_channel,
            )

            if copied:
                increment_message_counter(guild.id, copied)

            # Delete originals after a successful copy pass
            for msg in messages:
                try:
                    await msg.delete()
                except Exception:
                    pass  # Ignore undeletable messages

            await interaction.followup.send(
                f"Cut operation completed. {copied} of {len(messages)} messages moved.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "Missing permissions (Manage Messages required).",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                f"Error during cut operation: {e}",
                ephemeral=True,
            )


class CopyView(discord.ui.View):
    """
    UI container for the message copy interface.
    """

    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(CopyChannelSelect(message))


class CopyFromHereView(discord.ui.View):
    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(CopyFromHereChannelSelect(message))


class CutView(discord.ui.View):
    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(CutChannelSelect(message))
