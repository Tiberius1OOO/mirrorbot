"""
Plain-text export of channel/thread message bodies (same inclusion rules as EPUB).
"""

import re

import discord

from helpers.epub_generator import collect_messages


def safe_txt_filename(name: str, fallback: str = "channel_export") -> str:
    """ASCII-ish safe base name for a .txt file (no path separators)."""
    s = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"_+", "_", s).strip("._")
    return (s or fallback)[:80]


async def build_flowtext_export(
    source: discord.TextChannel | discord.Thread,
) -> tuple[str, int]:
    """
    Message bodies only, oldest → newest, separated by blank lines.
    Skips empty posts; same bot vs webhook rules as EPUB collection.
    """
    messages = await collect_messages(source)
    bodies = [m.content.strip() for m in messages]
    text = "\n\n".join(bodies)
    return text, len(messages)
