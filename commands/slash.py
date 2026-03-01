"""
Slash Command Registration
==========================

Registers all administrator slash commands for the bot.

Primary responsibilities:
• Setup and configuration commands
• Relay management commands
• Diagnostic commands
"""

import time
from datetime import datetime

import discord
from discord import app_commands

from helpers.database import (
    add_relay,
    get_connection,
    get_guild_config,
    remove_relay,
    set_error_channel,
)
from helpers.epub_generator import generate_epub


def register(tree, client):
    """
    Registers all slash commands with the command tree.
    """

    @tree.command(name="setup", description="Initial bot setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(interaction: discord.Interaction):
        """
        Initializes the bot configuration for the server.
        Sets the current channel as the error channel.
        """
        guild_id = interaction.guild.id

        set_error_channel(guild_id, interaction.channel.id)

        await interaction.response.send_message(
            "Setup complete. This channel is now the error channel.",
            ephemeral=True,
        )

    @tree.command(name="start_relay", description="Start a live relay")
    @app_commands.checks.has_permissions(administrator=True)
    async def start_relay(
        interaction: discord.Interaction,
        source: discord.TextChannel,
        target: discord.TextChannel,
        delay_seconds: int,
    ):
        """
        Creates a new relay from a source channel
        to a target channel.
        """
        guild_id = interaction.guild.id
        config = get_guild_config(guild_id)

        if not config:
            await interaction.response.send_message("Run /setup first.", ephemeral=True)
            return

        # Check if relay already exists
        for r in config["relays"]:
            if r["source"] == source.id:
                await interaction.response.send_message(
                    "Relay already exists.", ephemeral=True
                )
                return

        add_relay(guild_id, source.id, target.id, delay_seconds)

        await interaction.response.send_message(
            f"Relay started: {source.mention} → {target.mention}",
            ephemeral=True,
        )

    @tree.command(name="stop_relay", description="Stop a relay")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop_relay(interaction: discord.Interaction, source: discord.TextChannel):
        """
        Stops an existing relay from a source channel.
        """
        guild_id = interaction.guild.id
        config = get_guild_config(guild_id)

        if not config:
            await interaction.response.send_message("Run /setup first.", ephemeral=True)
            return

        remove_relay(guild_id, source.id)

        await interaction.response.send_message("Relay stopped.", ephemeral=True)

    @tree.command(name="instances", description="Show relays")
    @app_commands.checks.has_permissions(administrator=True)
    async def instances(interaction: discord.Interaction):
        """
        Displays all active relay configurations
        for the current server.
        """
        config = get_guild_config(interaction.guild.id)

        if not config or not config["relays"]:
            await interaction.response.send_message("No active relays.", ephemeral=True)
            return

        lines = []
        for r in config["relays"]:
            source = interaction.guild.get_channel(r["source"])
            target = interaction.guild.get_channel(r["target"])
            lines.append(f"{source.mention} → {target.mention}")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @tree.command(
        name="generate_book_beta",
        description="Generate a Beta EPUB (with post links)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def generate_book_beta(
        interaction: discord.Interaction,
        title: str,
        author: str,
        source_channel: discord.TextChannel,
        upload_channel: discord.TextChannel,
        invite_link: str,
        cover_image: discord.Attachment | None = None,
        summary: str = "",
        chapter_file: discord.Attachment | None = None,
    ):
        await interaction.response.defer(thinking=True)

        try:
            cover_bytes = await cover_image.read() if cover_image else None
            chapter_content = (
                (await chapter_file.read()).decode("utf-8") if chapter_file else None
            )

            result = await generate_epub(
                title=title,
                author=author,
                source_channel=source_channel,
                guild_id=interaction.guild.id,
                guild_name=interaction.guild.name,
                invite_link=invite_link,
                beta_mode=True,
                cover_bytes=cover_bytes,
                summary=summary,
                chapter_file_content=chapter_content,
            )

            writer_list = ", ".join(result["writers"])

            await upload_channel.send(
                content=(
                    f"📘 **BETA Book Generated**\n\n"
                    f"**Title:** {title}\n"
                    f"**Requested by:** {interaction.user.mention}\n"
                    f"**Word Count:** {result['word_count']}\n"
                    f"**Messages:** {result['message_count']}\n"
                    f"**Chapters:** {result['chapter_count']}\n"
                    f"**Writers:** {writer_list}"
                ),
                file=discord.File(result["path"]),
            )

            await interaction.followup.send(
                "Beta book successfully generated.",
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f"Error generating beta book: {e}",
                ephemeral=True,
            )

    @tree.command(
        name="generate_book",
        description="Generate a clean publication EPUB",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def generate_book(
        interaction: discord.Interaction,
        title: str,
        author: str,
        source_channel: discord.TextChannel,
        upload_channel: discord.TextChannel,
        invite_link: str,
        cover_image: discord.Attachment | None = None,
        summary: str = "",
        chapter_file: discord.Attachment | None = None,
    ):
        await interaction.response.defer(thinking=True)

        try:
            cover_bytes = await cover_image.read() if cover_image else None
            chapter_content = (
                (await chapter_file.read()).decode("utf-8") if chapter_file else None
            )

            result = await generate_epub(
                title=title,
                author=author,
                source_channel=source_channel,
                guild_id=interaction.guild.id,
                guild_name=interaction.guild.name,
                invite_link=invite_link,
                beta_mode=False,
                cover_bytes=cover_bytes,
                summary=summary,
                chapter_file_content=chapter_content,
            )

            writer_list = ", ".join(result["writers"])

            await upload_channel.send(
                content=(
                    f"📘 **Book Generated**\n\n"
                    f"**Title:** {title}\n"
                    f"**Requested by:** {interaction.user.mention}\n"
                    f"**Word Count:** {result['word_count']}\n"
                    f"**Messages:** {result['message_count']}\n"
                    f"**Chapters:** {result['chapter_count']}\n"
                    f"**Writers:** {writer_list}"
                ),
                file=discord.File(result["path"]),
            )

            await interaction.followup.send(
                "Book successfully generated.",
                ephemeral=True,
            )

        except Exception as e:
            await interaction.followup.send(
                f"Error generating book: {e}",
                ephemeral=True,
            )

    @tree.command(
        name="bot_info",
        description="Show detailed bot diagnostic information",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def bot_info(interaction: discord.Interaction):
        """
        Sends a structured diagnostic report using an embed.
        """
        guild = interaction.guild
        guild_id = guild.id
        user = interaction.user

        config = get_guild_config(guild_id)
        if not config:
            await interaction.response.send_message(
                "Setup not completed. Please run /setup first.",
                ephemeral=True,
            )
            return

        # Uptime calculation
        start_time = client.start_time
        uptime_seconds = int(time.time() - start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        uptime_str = f"{hours}h {minutes}m {seconds}s"
        start_time_str = datetime.fromtimestamp(start_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Relay info
        relays = config.get("relays", [])
        relay_lines = []
        for r in relays:
            source = guild.get_channel(r["source"])
            target = guild.get_channel(r["target"])

            source_name = source.name if source else f"Unknown({r['source']})"
            target_name = target.name if target else f"Unknown({r['target']})"

            relay_lines.append(f"{source_name} → {target_name} ({r['delay']}s)")

        relay_text = "\n".join(relay_lines) if relay_lines else "No active relays"

        # DB structure info
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM guilds")
        guild_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM relays")
        relay_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM stats")
        stats_count = cursor.fetchone()[0]

        conn.close()

        # Build embed
        embed = discord.Embed(
            title="DragonCopy Bot Status",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )

        embed.add_field(
            name="Server",
            value=f"{guild.name}\nID: {guild_id}",
            inline=False,
        )

        embed.add_field(
            name="User",
            value=f"{user} ({user.id})",
            inline=True,
        )

        embed.add_field(
            name="Members",
            value=str(guild.member_count),
            inline=True,
        )

        embed.add_field(
            name="Tracked Channels",
            value=str(len(relays)),
            inline=True,
        )

        embed.add_field(
            name="Bot Uptime",
            value=f"Started: {start_time_str}\nUptime: {uptime_str}",
            inline=False,
        )

        embed.add_field(
            name="Database",
            value=(
                f"Guild entries: {guild_count}\n"
                f"Relay entries: {relay_count}\n"
                f"Stats entries: {stats_count}"
            ),
            inline=False,
        )

        embed.add_field(
            name="Active Relays",
            value=relay_text,
            inline=False,
        )

        error_channel_id = config["error_channel"]
        channel = guild.get_channel(error_channel_id)

        if not channel:
            await interaction.response.send_message(
                "Error channel not found.",
                ephemeral=True,
            )
            return

        # Send embed to error channel
        await channel.send(embed=embed)

        # Confirm to the user
        await interaction.response.send_message(
            "Bot info sent to error channel.",
            ephemeral=True,
        )
