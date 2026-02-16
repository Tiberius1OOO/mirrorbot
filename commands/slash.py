"""
Slash Command Registration
==========================

Registers all administrator slash commands for the bot.

Primary responsibilities:
• Setup and configuration commands
• Relay management commands
• Diagnostic commands
"""

import discord
from discord import app_commands

from helpers.database import (
    add_relay,
    get_guild_config,
    remove_relay,
    set_error_channel,
)


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
        name="bot_info",
        description="Send bot diagnostic info to the error channel",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def bot_info(interaction: discord.Interaction):
        """
        Sends a diagnostic report to the configured
        error channel.
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

        relays = config.get("relays", [])

        # Build relay info
        if relays:
            relay_lines = []
            for r in relays:
                source = guild.get_channel(r["source"])
                target = guild.get_channel(r["target"])

                source_name = source.name if source else f"Unknown({r['source']})"
                target_name = target.name if target else f"Unknown({r['target']})"

                relay_lines.append(
                    f"{source_name} → {target_name} | Delay: {r['delay']}s"
                )

            relay_info = "\n".join(relay_lines)
        else:
            relay_info = "No active relays"

        total_copied = config["stats"]["messages_copied"]

        info_text = (
            "**Bot Info Dump**\n"
            f"- Relay Instances:\n{relay_info}\n\n"
            f"- Server ID:\n{guild_id}\n\n"
            f"- Command User:\n{user.id} - {user}\n\n"
            f"- Stats:\n"
            f"Messages copied total: {total_copied}"
        )

        error_channel_id = config["error_channel"]
        channel = guild.get_channel(error_channel_id)

        if not channel:
            await interaction.response.send_message(
                "Error channel not found.",
                ephemeral=True,
            )
            return

        await channel.send(info_text)

        await interaction.response.send_message(
            "Bot info sent to error channel.",
            ephemeral=True,
        )
