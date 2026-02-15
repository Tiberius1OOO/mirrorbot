import discord
from discord import app_commands

from helpers.config import load_and_prepare_config, save_config


def register(tree, client):

    @tree.command(name="setup", description="Initial bot setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(interaction: discord.Interaction):
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
