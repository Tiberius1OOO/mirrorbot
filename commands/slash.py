"""
Slash Command Registration
==========================

Registers all administrator slash commands for the bot.

Primary responsibilities:
• Setup and configuration commands
• Relay management commands
• Diagnostic commands

Architecture
------------
All slash commands are defined inside a single `register`
function. This function is called during bot startup and
attaches commands to the global command tree.

This design allows:
• Clean separation from the main bot file
• Modular command loading
• Easier future expansion (e.g., multiple command modules)

Command Categories
------------------
Setup:
    /setup
        Initializes the configuration for the server.

Relay Control:
    /start_relay
        Creates a live relay between channels.
    /stop_relay
        Stops an existing relay.
    /instances
        Displays all active relays.

Diagnostics:
    /bot_info
        Sends a detailed bot status report.
"""

import discord
from discord import app_commands

from helpers.config import load_and_prepare_config, save_config


def register(tree, client):
    """
    Registers all slash commands with the command tree.

    This function is called during bot startup and
    attaches commands to the global command system.

    Args:
        tree (app_commands.CommandTree):
            The bot's command tree.

        client (discord.Client):
            The main Discord client instance.
    """

    @tree.command(name="setup", description="Initial bot setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(interaction: discord.Interaction):
        """
        Initializes the bot configuration for the server.

        Sets the current channel as the error channel and
        creates the default configuration structure.

        Admin only.
        """
        guild_id = interaction.guild.id

        config = {
            "error_channel": interaction.channel.id,
            "relays": [],
            "stats": {"messages_copied": 0},
        }

        save_config(guild_id, config)

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

        Args:
            source:
                Channel to copy messages from.
            target:
                Channel to send relayed messages to.
            delay_seconds:
                Delay before messages are forwarded.

        Admin only.
        """
        guild_id = interaction.guild.id
        config = load_and_prepare_config(guild_id)

        if not config:
            await interaction.response.send_message("Run /setup first.", ephemeral=True)
            return

        for r in config["relays"]:
            if r["source"] == source.id:
                await interaction.response.send_message(
                    "Relay already exists.", ephemeral=True
                )
                return

        config["relays"].append(
            {"source": source.id, "target": target.id, "delay": delay_seconds}
        )
        save_config(guild_id, config)

        await interaction.response.send_message(
            f"Relay started: {source.mention} → {target.mention}",
            ephemeral=True,
        )

    @tree.command(name="stop_relay", description="Stop a relay")
    @app_commands.checks.has_permissions(administrator=True)
    async def stop_relay(interaction: discord.Interaction, source: discord.TextChannel):
        """
        Stops an existing relay from a source channel.

        Removes the relay configuration for the
        specified source channel.

        Args:
            source:
                The source channel of the relay to stop.

        Admin only.
        """
        guild_id = interaction.guild.id
        config = load_and_prepare_config(guild_id)

        if not config:
            return

        config["relays"] = [r for r in config["relays"] if r["source"] != source.id]
        save_config(guild_id, config)

        await interaction.response.send_message("Relay stopped.", ephemeral=True)

    @tree.command(name="instances", description="Show relays")
    @app_commands.checks.has_permissions(administrator=True)
    async def instances(interaction: discord.Interaction):
        """
        Displays all active relay configurations
        for the current server.

        Shows source and target channel pairs.

        Admin only.
        """
        config = load_and_prepare_config(interaction.guild.id)

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

        The report includes:
        • Active relay configurations
        • Server ID
        • Command issuer
        • Message copy statistics

        Useful for debugging and monitoring
        bot activity.

        Admin only.
        """
        guild = interaction.guild
        guild_id = guild.id
        user = interaction.user

        config = load_and_prepare_config(guild_id)
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
