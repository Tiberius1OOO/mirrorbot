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
    add_observed_channel,
    add_relay,
    get_connection,
    get_guild_config,
    get_top_relay_writers,
    get_total_relay_source_words,
    get_user_relay_word_rank,
    is_channel_observed,
    list_observed_channels,
    remove_observed_channel,
    remove_relay,
    set_error_channel,
)
from helpers.epub_generator import generate_epub, resolve_book_channel
from helpers.observe_backfill import backfill_observed_channel


def _truncate_field(text: str, limit: int = 1020) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


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
        name="observe",
        description="Start tracking words in a channel (full history scan, then live)",
    )
    @app_commands.describe(
        channel="Text/announcement channel or forum topic thread to observe",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def observe_command(
        interaction: discord.Interaction,
        channel: discord.TextChannel | discord.Thread,
    ):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        guild_id = guild.id

        try:
            ch = await resolve_book_channel(interaction.client, guild, channel)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        if is_channel_observed(guild_id, ch.id):
            await interaction.followup.send(
                f"Already observing {ch.mention}. Use `/unobserve` first to stop.",
                ephemeral=True,
            )
            return

        try:
            scanned, deltas = await backfill_observed_channel(guild_id, ch)
        except discord.Forbidden:
            await interaction.followup.send(
                "I need permission to read message history in that channel.",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(f"History scan failed: {e}", ephemeral=True)
            return

        add_observed_channel(guild_id, ch.id)
        words_added = sum(deltas.values())
        contributors = sum(1 for w in deltas.values() if w > 0)

        await interaction.followup.send(
            f"Now observing {ch.mention}.\n"
            f"• **{scanned}** messages processed this scan\n"
            f"• **{words_added:,}** words added from this scan, across **{contributors}** members\n"
            f"New messages there will keep counting until `/unobserve`.",
            ephemeral=True,
        )

    @tree.command(
        name="unobserve",
        description="Stop tracking words in a channel (keeps past totals & scan progress)",
    )
    @app_commands.describe(
        channel="Channel or thread to remove from the observe list",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def unobserve_command(
        interaction: discord.Interaction,
        channel: discord.TextChannel | discord.Thread,
    ):
        guild_id = interaction.guild.id
        try:
            ch = await resolve_book_channel(
                interaction.client, interaction.guild, channel
            )
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        if not is_channel_observed(guild_id, ch.id):
            await interaction.response.send_message(
                f"Not observing {ch.mention}.", ephemeral=True
            )
            return

        remove_observed_channel(guild_id, ch.id)
        await interaction.response.send_message(
            f"Stopped observing {ch.mention}. Word totals are unchanged; "
            f"re-observing later only counts **new** messages since the last scan.",
            ephemeral=True,
        )

    @tree.command(
        name="observing",
        description="List channels the bot is currently observing for word stats",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def observing_command(interaction: discord.Interaction):
        ids = list_observed_channels(interaction.guild.id)
        if not ids:
            await interaction.response.send_message(
                "No observed channels. Use `/observe` to add one.",
                ephemeral=True,
            )
            return
        lines = []
        for cid in ids:
            c = interaction.guild.get_channel(cid) or interaction.guild.get_thread(cid)
            lines.append(c.mention if c else f"`{cid}` (not in cache — try ID)")
        await interaction.response.send_message(
            "**Observed channels:**\n" + "\n".join(lines),
            ephemeral=True,
        )

    @tree.command(
        name="generate_book_beta",
        description="Generate a Beta EPUB (with post links)",
    )
    @app_commands.describe(
        source_channel="Text/announcement channel or a thread (e.g. forum topic) to export",
        upload_channel="Channel or thread where the EPUB file is posted",
        invite_link="Optional: permanent invite URL on the EPUB info page; leave empty to omit",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def generate_book_beta(
        interaction: discord.Interaction,
        title: str,
        author: str,
        source_channel: discord.TextChannel | discord.Thread,
        upload_channel: discord.TextChannel | discord.Thread,
        invite_link: str = "",
        cover_image: discord.Attachment | None = None,
        summary: str = "",
        chapter_file: discord.Attachment | None = None,
    ):
        await interaction.response.defer(thinking=True)

        try:
            source = await resolve_book_channel(
                interaction.client, interaction.guild, source_channel
            )
            upload = await resolve_book_channel(
                interaction.client, interaction.guild, upload_channel
            )
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        try:
            cover_bytes = await cover_image.read() if cover_image else None
            chapter_content = (
                (await chapter_file.read()).decode("utf-8") if chapter_file else None
            )

            result = await generate_epub(
                title=title,
                author=author,
                source_channel=source,
                guild_id=interaction.guild.id,
                guild_name=interaction.guild.name,
                invite_link=invite_link,
                beta_mode=True,
                guild=interaction.guild,
                cover_bytes=cover_bytes,
                summary=summary,
                chapter_file_content=chapter_content,
            )

            writer_list = ", ".join(result["writers"])

            await upload.send(
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
    @app_commands.describe(
        source_channel="Text/announcement channel or a thread (e.g. forum topic) to export",
        upload_channel="Channel or thread where the EPUB file is posted",
        invite_link="Optional: permanent invite URL on the EPUB info page; leave empty to omit",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def generate_book(
        interaction: discord.Interaction,
        title: str,
        author: str,
        source_channel: discord.TextChannel | discord.Thread,
        upload_channel: discord.TextChannel | discord.Thread,
        invite_link: str = "",
        cover_image: discord.Attachment | None = None,
        summary: str = "",
        chapter_file: discord.Attachment | None = None,
    ):
        await interaction.response.defer(thinking=True)

        try:
            source = await resolve_book_channel(
                interaction.client, interaction.guild, source_channel
            )
            upload = await resolve_book_channel(
                interaction.client, interaction.guild, upload_channel
            )
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

        try:
            cover_bytes = await cover_image.read() if cover_image else None
            chapter_content = (
                (await chapter_file.read()).decode("utf-8") if chapter_file else None
            )

            result = await generate_epub(
                title=title,
                author=author,
                source_channel=source,
                guild_id=interaction.guild.id,
                guild_name=interaction.guild.name,
                invite_link=invite_link,
                beta_mode=False,
                guild=interaction.guild,
                cover_bytes=cover_bytes,
                summary=summary,
                chapter_file_content=chapter_content,
            )

            writer_list = ", ".join(result["writers"])

            await upload.send(
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
        description="Your word stats and rank — admins see full bot diagnostics",
    )
    async def bot_info(interaction: discord.Interaction):
        """
        Everyone: personal card (avatar, join date, words in observed channels, rank).
        Administrators: same plus diagnostics, relays, observed list, leaderboard.
        """
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return

        guild_id = guild.id
        is_admin = interaction.user.guild_permissions.administrator

        member = interaction.member
        if member is None:
            try:
                member = await guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                member = interaction.user

        if hasattr(member, "joined_at") and member.joined_at:
            joined_str = member.joined_at.strftime("%Y-%m-%d %H:%M UTC")
        else:
            joined_str = "Unknown"

        words, rank, writers_on_board = get_user_relay_word_rank(
            guild_id, interaction.user.id
        )
        total_relay_words = get_total_relay_source_words(guild_id)

        if rank is None:
            rank_str = (
                "— (an admin must `/observe` a channel you write in, then post there)"
                if writers_on_board
                else "— (no `/observe` channels yet — admins: use `/observe`)"
            )
        else:
            rank_str = f"**#{rank}** of **{writers_on_board}** writers"

        user_embed = discord.Embed(
            title="DragonCopy — your stats",
            description=(
                "Counts only messages in **observed** channels/threads "
                "(admins add them with `/observe`). Webhook posts count like story exports."
            ),
            color=discord.Color.teal(),
            timestamp=datetime.utcnow(),
        )
        user_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        user_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        user_embed.add_field(name="Joined server", value=joined_str, inline=True)
        user_embed.add_field(
            name="Your words (observed)",
            value=f"**{words:,}**",
            inline=True,
        )
        user_embed.add_field(name="Rank", value=rank_str, inline=True)
        user_embed.add_field(
            name="Server total (observed)",
            value=f"**{total_relay_words:,}** words from all members",
            inline=False,
        )
        user_embed.set_footer(
            text="Ranking uses the same word counting as story EPUBs (split on whitespace)."
        )

        if not is_admin:
            await interaction.response.send_message(embed=user_embed, ephemeral=True)
            return

        config = get_guild_config(guild_id)
        if not config:
            user_embed.add_field(
                name="Administrator",
                value="This server has not run `/setup` yet. Relay diagnostics are unavailable until then.",
                inline=False,
            )
            await interaction.response.send_message(embed=user_embed, ephemeral=True)
            return

        start_time = client.start_time
        uptime_seconds = int(time.time() - start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"
        start_time_str = datetime.fromtimestamp(start_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        relays = config.get("relays", [])
        relay_lines = []
        for r in relays:
            source = guild.get_channel(r["source"])
            target = guild.get_channel(r["target"])
            src = source.mention if source else f"`{r['source']}`"
            tgt = target.mention if target else f"`{r['target']}`"
            relay_lines.append(f"• {src} → {tgt} — delay **{r['delay']}s**")
        relay_text = (
            "\n".join(relay_lines) if relay_lines else "*No relays — use `/start_relay`*"
        )

        top = get_top_relay_writers(guild_id, 10)
        top_lines = []
        for i, (uid, w) in enumerate(top, start=1):
            m = guild.get_member(uid)
            label = m.display_name if m else f"User `{uid}`"
            top_lines.append(f"{i}. **{label}** — {w:,} words")
        top_text = (
            "\n".join(top_lines) if top_lines else "*No words recorded from observed channels yet.*"
        )

        obs_ids = list_observed_channels(guild_id)
        obs_lines = []
        for oid in obs_ids:
            oc = guild.get_channel(oid) or guild.get_thread(oid)
            obs_lines.append(oc.mention if oc else f"`{oid}`")
        obs_text = (
            "\n".join(f"• {x}" for x in obs_lines)
            if obs_lines
            else "*None — use `/observe`*"
        )

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM guilds")
        guild_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM relays")
        relay_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM stats")
        stats_count = cursor.fetchone()[0]
        conn.close()

        admin_embed = discord.Embed(
            title="DragonCopy — administrator diagnostics",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        admin_embed.add_field(
            name="Server",
            value=f"{guild.name}\nID: `{guild_id}`",
            inline=False,
        )
        admin_embed.add_field(
            name="Invoked by",
            value=f"{interaction.user.mention}\n`{interaction.user.id}`",
            inline=True,
        )
        admin_embed.add_field(
            name="Members",
            value=str(guild.member_count),
            inline=True,
        )
        admin_embed.add_field(
            name="Relay instances",
            value=f"**{len(relays)}** active (source → target pairs)",
            inline=True,
        )
        admin_embed.add_field(
            name="Words (/observe channels)",
            value=(
                f"**{total_relay_words:,}** total (all members)\n"
                f"**{writers_on_board}** members on leaderboard"
            ),
            inline=False,
        )
        admin_embed.add_field(
            name=f"Observed channels ({len(obs_ids)})",
            value=_truncate_field(obs_text),
            inline=False,
        )
        admin_embed.add_field(
            name="Bot uptime",
            value=f"Started: {start_time_str}\nUptime: {uptime_str}",
            inline=False,
        )
        admin_embed.add_field(
            name="Database",
            value=(
                f"Guild rows: {guild_count}\n"
                f"Relay rows: {relay_count}\n"
                f"Stats rows: {stats_count}"
            ),
            inline=True,
        )
        admin_embed.add_field(
            name="Messages mirrored (counter)",
            value=str(config["stats"].get("messages_copied", 0)),
            inline=True,
        )
        admin_embed.add_field(
            name="Active relays (channels)",
            value=_truncate_field(relay_text),
            inline=False,
        )
        admin_embed.add_field(
            name="Top writers (observed)",
            value=_truncate_field(top_text),
            inline=False,
        )

        await interaction.response.send_message(
            embeds=[user_embed, admin_embed],
            ephemeral=True,
        )
