"""
Per-channel shared notes (slash group ``/notes``).

• ``/notes open`` — ephemeral notepad + **Edit** (only you see it).
• ``/notes info`` — full guide (Markdown, limits, privacy).

After saving from the modal, run ``/notes open`` again to load the latest text
(ephemeral messages are not edited in place).

Stored text is one shared pad per channel; edits are not attributed to users.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from helpers.database import get_channel_note, set_channel_note

if TYPE_CHECKING:
    from typing import Protocol

    class _ClientWithStartTime(Protocol):
        start_time: float


MAX_NOTE_CHARS = 4000
_BTN_PREFIX = "dcn:b:"
_MOD_PREFIX = "dcn:m:"


def _button_custom_id(guild_id: int, channel_id: int) -> str:
    return f"{_BTN_PREFIX}{guild_id}:{channel_id}:0"


def _modal_custom_id(guild_id: int, channel_id: int, message_id: int) -> str:
    return f"{_MOD_PREFIX}{guild_id}:{channel_id}:{message_id}"


def _build_embed(
    channel: discord.abc.GuildChannel | discord.Thread,
    body: str,
) -> discord.Embed:
    placeholder = "*No notes yet.* Click **Edit** below to add something for this channel."
    text = body.strip() if body else ""
    desc = text if text else placeholder
    if len(desc) > 4096:
        suffix = "\n*(Preview trimmed — full text remains saved up to the editor limit.)*"
        desc = desc[: 4096 - len(suffix)] + suffix

    embed = discord.Embed(
        title="Channel notepad",
        description=desc,
        color=discord.Color.dark_teal(),
    )
    ch_label = channel.mention if hasattr(channel, "mention") else f"#{channel.name}"
    embed.add_field(name="Scope", value=ch_label, inline=True)
    embed.set_footer(text="Use /notes info to get an explanation about how to write a note.")
    return embed


def _build_info_embeds(bot_user: discord.ClientUser | discord.User) -> list[discord.Embed]:
    """Long-form help for `/notes info` — modern, readable, ephemeral-only in the handler."""
    accent = discord.Color.from_rgb(67, 181, 129)
    accent2 = discord.Color.from_rgb(99, 102, 241)

    intro = discord.Embed(
        title="Channel notes",
        description=(
            "A **single shared draft** for this channel or thread: everyone reads and edits the "
            "same text, but **only you** ever see these panels — replies are **ephemeral** and "
            "never post in the story channel.\n\n"
            "**Commands**\n"
            "• **`/notes open`** — notepad + **Edit** button\n"
            "• **`/notes info`** — this guide\n\n"
            "_Discord nests slash commands: type `/notes`, then pick **open** or **info**._"
        ),
        color=accent,
    )
    intro.set_author(name="DragonCopy notes", icon_url=bot_user.display_avatar.url)
    intro.add_field(
        name="How editing works",
        value=(
            "1. Run **`/notes open`** where the RP lives.\n"
            "2. Click **Edit**, write in the modal, then **Submit**.\n"
            "3. Run **`/notes open`** again to see the latest text after you save."
        ),
        inline=False,
    )
    intro.add_field(
        name="Privacy",
        value=(
            "• Ephemeral: **no one else** sees your card, buttons, or saves.\n"
            "• The **saved text** is still shared: anyone can open the pad and change it.\n"
            "• The bot does **not** record which user last edited the note."
        ),
        inline=False,
    )

    md = discord.Embed(
        title="Markdown you can use",
        description=(
            "In the editor, Discord renders normal chat Markdown in the notepad preview. "
            "Below: **result** — how to type it."
        ),
        color=accent2,
    )
    md.add_field(
        name="Emphasis",
        value=(
            "**Bold** — `**text**`\n"
            "*Italic* — `*text*` or `_text_`\n"
            "***Both*** — `***text***`\n"
            "__Underline__ — `__text__`\n"
            "~~Strike~~ — `~~text~~`\n"
            "||Spoiler|| — `||hidden||` (tap to reveal)"
        ),
        inline=True,
    )
    md.add_field(
        name="Code",
        value=(
            "`Inline` — single grave accents around text\n"
            "Fenced block — a line containing only **three** grave accents, your lines, "
            "then a closing line of three (same style as Discord chat)."
        ),
        inline=True,
    )
    md.add_field(
        name="Structure",
        value=(
            "# Heading — `#` at line start\n"
            "## Smaller — `##`\n"
            "> Quote — `>` at line start\n"
            "• List — `- item` per line\n"
            "1. Numbered — `1.` at line start"
        ),
        inline=True,
    )
    md.add_field(
        name="Links & breaks",
        value=(
            "`[label](https://example.com)` — clickable link\n"
            "Blank line between paragraphs, or two spaces at the end of a line for a soft break."
        ),
        inline=False,
    )
    md.set_footer(
        text=f"Editor limit: {MAX_NOTE_CHARS} characters (Discord modal cap). "
        "One note per channel — the bot does not split long notes into multiple messages."
    )

    return [intro, md]


async def _apply_saved_notes(
    interaction: discord.Interaction,
    guild_id: int,
    channel_id: int,
    _message_id: int,
    raw: str,
) -> None:
    if interaction.response.is_done():
        return

    if len(raw) > MAX_NOTE_CHARS:
        raw = raw[:MAX_NOTE_CHARS]

    set_channel_note(guild_id, channel_id, raw)

    await interaction.response.send_message(
        "Notes saved — use `/notes open` to view your note.",
        ephemeral=True,
    )


class _NotesEditModal(discord.ui.Modal):
    def __init__(
        self,
        guild_id: int,
        channel_id: int,
        message_id: int,
        current: str,
    ):
        super().__init__(
            title="Edit channel notes",
            custom_id=_modal_custom_id(guild_id, channel_id, message_id),
        )
        self._guild_id = guild_id
        self._channel_id = channel_id
        self._message_id = message_id

        self._body = discord.ui.TextInput(
            label="Notes (Markdown)",
            style=discord.TextStyle.paragraph,
            default=current[:MAX_NOTE_CHARS] if current else "",
            required=False,
            max_length=MAX_NOTE_CHARS,
            placeholder=f"Up to {MAX_NOTE_CHARS} characters. Use /notes info for Markdown help.",
        )
        self.add_item(self._body)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = str(self._body.value) if self._body.value else ""
        await _apply_saved_notes(
            interaction, self._guild_id, self._channel_id, self._message_id, raw
        )


class _EditNotesButton(discord.ui.Button):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(
            label="Edit",
            style=discord.ButtonStyle.primary,
            custom_id=_button_custom_id(guild_id, channel_id),
        )
        self._guild_id = guild_id
        self._channel_id = channel_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await _open_notes_modal(interaction, self._guild_id, self._channel_id)


async def _open_notes_modal(
    interaction: discord.Interaction, guild_id: int, channel_id: int
) -> None:
    if interaction.response.is_done():
        return
    if interaction.guild is None or interaction.guild.id != guild_id:
        await interaction.response.send_message(
            "This notepad belongs to another server.", ephemeral=True
        )
        return
    if interaction.message is None:
        await interaction.response.send_message("Missing message context.", ephemeral=True)
        return

    text = get_channel_note(guild_id, channel_id) or ""
    await interaction.response.send_modal(
        _NotesEditModal(guild_id, channel_id, interaction.message.id, text)
    )


class NotesView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=None)
        self.add_item(_EditNotesButton(guild_id, channel_id))


def register_notes_command(tree: app_commands.CommandTree, client: _ClientWithStartTime) -> None:
    notes = app_commands.Group(
        name="notes",
        description="Shared channel notepad (ephemeral — only you see the panels).",
    )

    async def _notes_open_impl(interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Use this command inside a server.", ephemeral=True
            )
            return

        channel = interaction.channel
        if not isinstance(
            channel,
            (discord.TextChannel, discord.Thread, discord.ForumChannel),
        ):
            await interaction.response.send_message(
                "Notes are only available in text channels, forum channels, and threads.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id
        channel_id = channel.id
        body = get_channel_note(guild_id, channel_id) or ""
        embed = _build_embed(channel, body)
        view = NotesView(guild_id, channel_id)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @notes.command(
        name="open",
        description="Open the notepad: current text, Edit button (only you see this).",
    )
    async def notes_open(interaction: discord.Interaction):
        await _notes_open_impl(interaction)

    @notes.command(
        name="info",
        description="Full guide: commands, Markdown, limits, and privacy.",
    )
    async def notes_info(interaction: discord.Interaction):
        if interaction.client.user is None:
            await interaction.response.send_message(
                "Bot user not ready yet — try again in a moment.", ephemeral=True
            )
            return
        embeds = _build_info_embeds(interaction.client.user)
        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    _ = client
    tree.add_command(notes)
