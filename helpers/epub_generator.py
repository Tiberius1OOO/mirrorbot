import asyncio
import html
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import discord
from ebooklib import epub


# =========================================================
# MARKDOWN CONVERSION
# =========================================================


def convert_discord_markdown_to_html(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    code_block_pattern = r"```(\w+)?\n(.*?)```"

    def replace_code_block(match):
        language = match.group(1) or ""
        code_content = match.group(2)
        return (
            f'<pre class="code-block"><code class="language-{language}">'
            f"{code_content}"
            "</code></pre>"
        )

    text = re.sub(code_block_pattern, replace_code_block, text, flags=re.DOTALL)

    text = text.replace("\r\n", "\n")
    text = text.replace("\n", "<br/>")

    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)\*(?<!\*)", r"<em>\1</em>", text)
    text = re.sub(r"__(.*?)__", r"<u>\1</u>", text)

    return text


# =========================================================
# CHAPTER FILE PARSER
# =========================================================


def parse_chapter_file(content: str) -> Dict[int, str]:
    chapter_map = {}
    pattern = r'^(\d+),"(.+)"$'

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line)
        if match:
            message_id = int(match.group(1))
            title = match.group(2)
            chapter_map[message_id] = title

    return chapter_map


# =========================================================
# MESSAGE COLLECTION
# =========================================================


def _is_forum_parent_channel(ch: Any) -> bool:
    """True if this is a forum (or media) listing channel, not a post/thread."""
    t = getattr(ch, "type", None)
    if t is not None:
        ct = discord.ChannelType
        # discord.py uses ``forum``; some versions also expose ``guild_forum`` / ``media``
        for name in ("forum", "guild_forum", "media"):
            if hasattr(ct, name) and t == getattr(ct, name):
                return True
    return isinstance(ch, discord.ForumChannel)


async def resolve_book_channel(
    client: discord.Client,
    guild: Optional[discord.Guild],
    channel: discord.abc.GuildChannel | discord.Thread | Any,
) -> discord.TextChannel | discord.Thread:
    """
    Ensure we have a full TextChannel or Thread (slash picks may be partial).
    Rejects forum/media parents — export must target a thread or text channel.
    """
    if _is_forum_parent_channel(channel):
        raise ValueError(
            "Choose a **forum post** (open the topic — it is a thread), not the forum "
            "channel itself."
        )
    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        return channel
    if guild is None:
        raise ValueError("Book export must be used in a server.")

    full = guild.get_channel_or_thread(channel.id)
    if _is_forum_parent_channel(full):
        raise ValueError(
            "Choose a **forum post** (the topic thread), not the forum channel listing."
        )
    if isinstance(full, (discord.TextChannel, discord.Thread)):
        return full

    fetched = await client.fetch_channel(channel.id)
    if _is_forum_parent_channel(fetched):
        raise ValueError(
            "Choose a **forum post** (the topic thread), not the forum channel listing."
        )
    if isinstance(fetched, (discord.TextChannel, discord.Thread)):
        return fetched

    raise ValueError(
        "Unsupported channel type. Use a text channel, announcement channel, or a thread "
        "(e.g. a forum topic)."
    )


async def collect_messages(source_channel: discord.TextChannel | discord.Thread):
    messages = []

    async for message in source_channel.history(limit=None, oldest_first=True):
        await asyncio.sleep(0)

        # Skip real bot messages but allow webhook messages
        if message.author.bot and not message.webhook_id:
            continue

        content = message.content.strip()
        if not content:
            continue

        messages.append(message)

    return messages


# =========================================================
# RENDER MESSAGE HTML
# =========================================================


def render_messages(messages, chapter_map: Dict[int, str], beta_mode: bool):

    chapters = []
    current_chapter = []
    chapter_count = 0

    writers: Dict[int, dict] = {}
    writer_ids: List[int] = []
    word_count = 0
    message_count = 0
    first_timestamp = None
    last_timestamp = None

    for message in messages:

        if not first_timestamp:
            first_timestamp = message.created_at
        last_timestamp = message.created_at

        display_name = message.author.display_name
        avatar_url = message.author.display_avatar.url
        uid = message.author.id

        if uid not in writers:
            writers[uid] = {
                "display_name": display_name,
                "avatar_url": avatar_url,
            }
            writer_ids.append(uid)

        if message.id in chapter_map:
            if current_chapter:
                chapters.append(current_chapter)
                current_chapter = []

            chapter_count += 1
            chapter_title = chapter_map[message.id]

            header = (
                f'<h2 class="chapter-title">'
                f"Chapter {chapter_count} – {chapter_title}"
                f"</h2>"
            )
            current_chapter.append(header)

        content = message.content.strip()
        html_text = convert_discord_markdown_to_html(content)

        word_count += len(content.split())
        message_count += 1

        paragraph = f"<p>{html_text}</p>"
        current_chapter.append(paragraph)

        if beta_mode:
            link_html = (
                f'<div class="post-link">'
                f'<em>↳ <a href="{message.jump_url}">To Post</a></em>'
                f"</div>"
            )
            current_chapter.append(link_html)

    if current_chapter:
        chapters.append(current_chapter)

    if not chapters:
        chapters = [[]]

    return {
        "chapters": chapters,
        "writers": writers,
        "writer_ids": writer_ids,
        "word_count": word_count,
        "message_count": message_count,
        "start_date": first_timestamp,
        "end_date": last_timestamp,
    }


# =========================================================
# WRITER INFO (INFO PAGE)
# =========================================================


def _format_discord_handle(user: discord.abc.User) -> str:
    """Unique @username (legacy users include discriminator when not 0)."""
    if user.discriminator != "0":
        return f"@{user.name}#{user.discriminator}"
    return f"@{user.name}"


def _format_joined(member: Optional[discord.Member]) -> str:
    if member is None or member.joined_at is None:
        return "Unknown"
    return member.joined_at.strftime("%d.%m.%Y")


async def _resolve_member(guild: Optional[discord.Guild], user_id: int) -> Optional[discord.Member]:
    if guild is None:
        return None
    m = guild.get_member(user_id)
    if m is not None:
        return m
    try:
        return await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


# =========================================================
# EPUB BUILDER
# =========================================================


async def generate_epub(
    *,
    title: str,
    author: str,
    source_channel: discord.TextChannel | discord.Thread,
    guild_id: int,
    guild_name: str,
    invite_link: str = "",
    beta_mode: bool,
    guild: Optional[discord.Guild] = None,
    cover_bytes: Optional[bytes] = None,
    summary: str = "",
    chapter_file_content: Optional[str] = None,
):

    messages = await collect_messages(source_channel)

    if not messages:
        raise ValueError("No valid messages found in channel.")

    chapter_map = {}
    if chapter_file_content:
        chapter_map = parse_chapter_file(chapter_file_content)

    rendered = render_messages(messages, chapter_map, beta_mode)

    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    # Metadata
    book.add_metadata("DC", "guild_id", str(guild_id))
    book.add_metadata("DC", "source_channel_id", str(source_channel.id))
    book.add_metadata("DC", "generated_at", datetime.utcnow().isoformat())

    if beta_mode:
        book.add_metadata("DC", "beta_mode", "true")
    else:
        book.add_metadata("DC", "service_provided_by", "@tiberia")

    # CSS (EPUB-safe layout, no flexbox)
    style = """
    body { font-family: serif; }

    h1 { text-align: center; font-size: 2.5em; }

    h2.chapter-title {
        text-align: center;
        margin-top: 3em;
        margin-bottom: 2em;
        font-weight: bold;
        page-break-before: always;
    }

    p { margin-bottom: 1em; line-height: 1.5em; }

    .post-link {
        margin-top: 0.3em;
        margin-bottom: 1.2em;
        opacity: 0.65;
    }

    .author-row {
        display: table;
        width: 100%;
        margin-bottom: 1.25em;
        page-break-inside: avoid;
    }

    .author-row .avatar-cell {
        display: table-cell;
        width: 5.5em;
        vertical-align: top;
    }

    .author-row .text-cell {
        display: table-cell;
        vertical-align: top;
        padding-left: 0.75em;
    }

    .author-avatar {
        width: 5em;
        height: 5em;
        max-width: 5em;
        max-height: 5em;
        object-fit: cover;
        border-radius: 50%;
        border: 1px solid #999;
        display: block;
    }

    .author-line {
        margin: 0 0 0.35em 0;
        line-height: 1.35em;
    }

    .code-block {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 15px;
        border-radius: 6px;
        font-family: monospace;
        font-size: 0.9em;
        overflow-x: auto;
        margin-bottom: 1.5em;
    }
    """

    book.add_item(
        epub.EpubItem(
            uid="style",
            file_name="style.css",
            media_type="text/css",
            content=style,
        )
    )

    # Cover
    if cover_bytes:
        book.set_cover("cover.jpg", cover_bytes)

    # Title Page
    title_page = epub.EpubHtml(title="Title", file_name="title.xhtml")
    cover_html = ""
    if cover_bytes:
        cover_html = '<div style="text-align:center;"><img src="cover.jpg"/></div>'

    title_page.content = f"""
    {cover_html}
    <h1>{title}</h1>
    <h3 style="text-align:center;">{author}</h3>
    """
    book.add_item(title_page)

    # Info Page
    writers_html = ""

    import aiohttp

    writer_ids = rendered.get("writer_ids") or list(rendered["writers"].keys())
    resolved_by_id: Dict[int, Optional[discord.Member]] = {}

    async with aiohttp.ClientSession() as session:
        for uid in writer_ids:
            writer = rendered["writers"][uid]
            member = await _resolve_member(guild, uid)
            resolved_by_id[uid] = member

            display_name = (
                member.display_name if member is not None else writer["display_name"]
            )
            if member is not None:
                handle_text = _format_discord_handle(member)
                joined_text = _format_joined(member)
            else:
                handle_text = "Not in server (webhook or left server)"
                joined_text = "Unknown"

            avatar_url = writer["avatar_url"]
            safe_name = html.escape(display_name, quote=True)
            safe_handle = html.escape(handle_text, quote=True)
            safe_joined = html.escape(joined_text, quote=True)

            img_html = ""
            try:
                async with session.get(avatar_url) as resp:
                    avatar_bytes = await resp.read()

                filename = f"avatar_{uid}.jpg"

                book.add_item(
                    epub.EpubItem(
                        uid=f"avatar_{uid}",
                        file_name=f"images/{filename}",
                        media_type="image/jpeg",
                        content=avatar_bytes,
                    )
                )

                img_html = (
                    f'<img src="images/{filename}" class="author-avatar" alt="" />'
                )
            except Exception:
                img_html = '<div class="author-avatar"></div>'

            writers_html += f"""
            <div class="author-row">
                <div class="avatar-cell">{img_html}</div>
                <div class="text-cell">
                    <p class="author-line"><strong>Discord name:</strong> {safe_name}</p>
                    <p class="author-line"><strong>Discord @:</strong> {safe_handle}</p>
                    <p class="author-line"><strong>Joined:</strong> {safe_joined}</p>
                </div>
            </div>
            """

    timespan = "N/A"
    if rendered["start_date"] and rendered["end_date"]:
        timespan = (
            f"{rendered['start_date'].strftime('%d.%m.%Y')} – "
            f"{rendered['end_date'].strftime('%d.%m.%Y')}"
        )

    safe_guild = html.escape(guild_name, quote=True)
    invite_html = ""
    if invite_link.strip():
        safe_invite = html.escape(invite_link.strip(), quote=True)
        invite_html = f'<br/><a href="{safe_invite}">{safe_invite}</a>'

    info_page = epub.EpubHtml(title="Info", file_name="info.xhtml")
    info_page.content = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Info</title>
<link href="style.css" rel="stylesheet" type="text/css"/>
</head>
<body>
<h2>Generated from</h2>
<p style="text-align:center;">
<strong>{safe_guild}</strong>{invite_html}
</p>
<hr/>
<h2>Writers</h2>
{writers_html}
<hr/>
<p><strong>Word Count:</strong> {rendered["word_count"]}</p>
<p><strong>Total Messages:</strong> {rendered["message_count"]}</p>
<p><strong>Timespan:</strong> {html.escape(timespan, quote=True)}</p>
</body>
</html>"""
    book.add_item(info_page)

    # Chapters
    chapter_items = []
    for i, chapter_content in enumerate(rendered["chapters"], start=1):
        chapter = epub.EpubHtml(title=f"Chapter {i}", file_name=f"chap_{i}.xhtml")
        chapter.content = "".join(chapter_content)
        book.add_item(chapter)
        chapter_items.append(chapter)

    # Summary
    if summary:
        summary_page = epub.EpubHtml(title="Summary", file_name="summary.xhtml")
        summary_page.content = f"<h2>Summary</h2><p>{summary}</p>"
        book.add_item(summary_page)
        chapter_items.append(summary_page)

    book.toc = [title_page, info_page] + chapter_items
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", title_page, info_page] + chapter_items

    # Folder isolation
    guild_folder = os.path.join("data", str(guild_id))
    os.makedirs(guild_folder, exist_ok=True)

    for f in os.listdir(guild_folder):
        if f.endswith(".epub"):
            os.remove(os.path.join(guild_folder, f))

    safe_title = title.replace(" ", "_")

    if beta_mode:
        filename = f"BETA-{safe_title}-{guild_id}.epub"
    else:
        filename = f"{safe_title}.epub"

    output_path = os.path.join(guild_folder, filename)
    epub.write_epub(output_path, book)

    display_names_out = [
        (
            resolved_by_id[uid].display_name
            if resolved_by_id.get(uid)
            else rendered["writers"][uid]["display_name"]
        )
        for uid in writer_ids
    ]

    return {
        "path": output_path,
        "word_count": rendered["word_count"],
        "message_count": rendered["message_count"],
        "writers": display_names_out,
        "chapter_count": len(rendered["chapters"]),
    }
