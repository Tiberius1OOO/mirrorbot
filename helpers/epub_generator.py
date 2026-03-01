import asyncio
import os
import re
import uuid
from datetime import datetime
from typing import Dict, Optional

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


async def collect_messages(source_channel):
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

    writers = {}  # normalized by display_name.lower()
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

        writer_key = display_name.lower()

        if writer_key not in writers:
            writers[writer_key] = {
                "display_name": display_name,
                "avatar_url": avatar_url,
            }

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
        "word_count": word_count,
        "message_count": message_count,
        "start_date": first_timestamp,
        "end_date": last_timestamp,
    }


# =========================================================
# EPUB BUILDER
# =========================================================


async def generate_epub(
    *,
    title: str,
    author: str,
    source_channel,
    guild_id: int,
    guild_name: str,
    invite_link: str,
    beta_mode: bool,
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

    .author-block {
        margin-bottom: 25px;
        clear: both;
    }

    .author-avatar {
        float: left;
        width: 70px;
        height: 70px;
        border-radius: 50%;
        margin-right: 15px;
    }

    .author-info {
        overflow: hidden;
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

    async with aiohttp.ClientSession() as session:
        for key, writer in rendered["writers"].items():
            display_name = writer["display_name"]
            avatar_url = writer["avatar_url"]

            try:
                async with session.get(avatar_url) as resp:
                    avatar_bytes = await resp.read()

                filename = f"avatar_{key}.jpg"

                book.add_item(
                    epub.EpubItem(
                        uid=f"avatar_{key}",
                        file_name=f"images/{filename}",
                        media_type="image/jpeg",
                        content=avatar_bytes,
                    )
                )

                writers_html += f"""
                <div class="author-block">
                    <img src="images/{filename}" class="author-avatar"/>
                    <div class="author-info">
                        <strong>{display_name}</strong>
                    </div>
                </div>
                """

            except Exception:
                writers_html += f"<p><strong>{display_name}</strong></p>"

    timespan = "N/A"
    if rendered["start_date"] and rendered["end_date"]:
        timespan = (
            f"{rendered['start_date'].strftime('%d.%m.%Y')} – "
            f"{rendered['end_date'].strftime('%d.%m.%Y')}"
        )

    info_page = epub.EpubHtml(title="Info", file_name="info.xhtml")
    info_page.content = f"""
    <h2>Generated from</h2>
    <p style="text-align:center;">
        <strong>{guild_name}</strong><br/>
        <a href="{invite_link}">{invite_link}</a>
    </p>

    <hr/>

    <h2>Writers</h2>
    {writers_html}

    <hr/>

    <p><strong>Word Count:</strong> {rendered["word_count"]}</p>
    <p><strong>Total Messages:</strong> {rendered["message_count"]}</p>
    <p><strong>Timespan:</strong> {timespan}</p>
    """
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

    return {
        "path": output_path,
        "word_count": rendered["word_count"],
        "message_count": rendered["message_count"],
        "writers": [w["display_name"] for w in rendered["writers"].values()],
        "chapter_count": len(rendered["chapters"]),
    }
