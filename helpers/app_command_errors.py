"""
User-facing messages when application command permission checks fail.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands

_log = logging.getLogger(__name__)


def _command_label(interaction: discord.Interaction) -> str:
    cmd = interaction.command
    if cmd is None:
        return "This command"
    if isinstance(cmd, app_commands.ContextMenu):
        return f"**{cmd.name}** (Apps / right-click menu)"
    return f"`/{cmd.name}`"


def _command_purpose_line(interaction: discord.Interaction) -> str:
    cmd = interaction.command
    if cmd is None:
        return "No description is available."
    desc = (getattr(cmd, "description", None) or "").strip()
    return desc if desc else "No short description is available for this command."


def _missing_perm_phrase(missing_permissions: list[str]) -> str:
    parts = [
        p.replace("_", " ").replace("guild", "server").title()
        for p in missing_permissions
    ]
    if len(parts) == 1:
        return f"the **{parts[0]}** permission"
    return "**" + "**, **".join(parts) + "** permissions"


async def respond_app_command_permission_denied(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> bool:
    """
    If ``error`` is a user-facing permission / check failure, send an ephemeral
    explanation and return True. Otherwise return False (caller may log / ignore).
    """
    err: app_commands.AppCommandError = error
    if isinstance(error, app_commands.CommandInvokeError):
        inner = error.original
        if isinstance(inner, app_commands.AppCommandError):
            err = inner

    if isinstance(err, app_commands.MissingPermissions):
        perm_phrase = _missing_perm_phrase(err.missing_permissions)
        body = (
            f"You tried to run {_command_label(interaction)}, which requires "
            f"{perm_phrase} in this server. Your account does not have that here, "
            "so the bot will not run it.\n\n"
            "**What it is for:**\n"
            f"{_command_purpose_line(interaction)}\n\n"
            "If you need this done, ask someone whose role includes those permissions "
            "(often a **server administrator**)."
        )
    elif isinstance(err, app_commands.NoPrivateMessage):
        body = (
            f"{_command_label(interaction)} can only be used inside a server, "
            "not in direct messages."
        )
    elif isinstance(err, (app_commands.MissingRole, app_commands.MissingAnyRole)):
        body = (
            f"You tried to run {_command_label(interaction)}, but your account "
            "does not have the required role for that action in this server.\n\n"
            "**What it is for:**\n"
            f"{_command_purpose_line(interaction)}\n\n"
            "Ask a moderator or admin if you need help."
        )
    elif isinstance(err, app_commands.BotMissingPermissions):
        perm_phrase = _missing_perm_phrase(err.missing_permissions)
        body = (
            f"{_command_label(interaction)} needs the bot to have {perm_phrase} in this "
            "server or channel. A server admin must adjust **roles / channel permissions** "
            "for the bot, then try again."
        )
    elif isinstance(err, app_commands.CheckFailure):
        body = (
            f"You tried to run {_command_label(interaction)}, but a permission "
            "check failed (this command is limited to certain members or contexts).\n\n"
            "**What it is for:**\n"
            f"{_command_purpose_line(interaction)}\n\n"
            "Ask a **server administrator** if you believe you should have access."
        )
    else:
        return False

    embed = discord.Embed(
        title="You can't use this command here",
        description=body,
        color=discord.Color.orange(),
    )
    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except discord.HTTPException as e:
        _log.warning("Failed to send permission-denied embed: %s", e)
    return True
