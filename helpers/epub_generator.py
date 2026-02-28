import asyncio
import os
import re
import uuid
from datetime import datetime

from ebooklib import epub


def convert_discord_markdown_to_html(text: str) -> str:
    """
    Converts Discord markdown to HTML.
    Supports:
    - Bold
    - Italic
    - Underline
    - Line breaks
    - Code blocks with optional language
    """

    # Escape HTML first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Handle code blocks first (triple backticks)
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

    # Preserve line breaks
    text = text.replace("\r\n", "\n")
    text = text.replace("\n", "<br/>")

    # Bold
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)

    # Italic (safe version)
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)\*(?<!\*)", r"<em>\1</em>", text)

    # Underline
    text = re.sub(r"__(.*?)__", r"<u>\1</u>", text)

    return text


async def generate_epub(
    title: str,
    author: str,
    summary: str,
    cover_bytes: bytes,
    collected_data: dict,
    guild_name: str,
    invite_link: str,
):
    """
    Generates an EPUB file and returns the filepath.
    """

    book = epub.EpubBook()

    # Unique ID
    book_id = str(uuid.uuid4())
    book.set_identifier(book_id)
    book.set_title(title)
    book.set_language("en")
    book.add_author(author)

    # Add cover
    book.set_cover("cover.jpg", cover_bytes)

    # Basic CSS
    style = """
    body {
    font-family: serif;
    }

    h1 {
    text-align: center;
    font-size: 2.5em;
    }

    h2 {
    text-align: center;
    margin-top: 2em;
    }

    p {
    margin-bottom: 1em;
    line-height: 1.4em;
    }
    
    hr {
    margin: 2em 0;
    }

    .author-block {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    }

    .author-avatar {
    width: 70px;
    height: 70px;
    border-radius: 50%;
    margin-right: 15px;
    }

    .author-text {
    font-size: 1em;
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

    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content=style,
    )
    book.add_item(nav_css)

    # Title Page
    title_page = epub.EpubHtml(title="Title", file_name="title.xhtml")
    title_page.content = f"""
    <h1>{title}</h1>
    <h3 style="text-align:center;">{author}</h3>
    """
    book.add_item(title_page)

    # Info Page
    writers = collected_data["writers"]
    writers_html = ""

    for user_id, (display_name, tag, avatar_url) in writers.items():

        # Download avatar
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    avatar_bytes = await resp.read()

            avatar_filename = f"avatar_{user_id}.jpg"
            book.add_item(
                epub.EpubItem(
                    uid=f"avatar_{user_id}",
                    file_name=f"images/{avatar_filename}",
                    media_type="image/jpeg",
                    content=avatar_bytes,
                )
            )

            avatar_path = f"images/{avatar_filename}"

        except Exception:
            avatar_path = None

        # Build HTML block
        if avatar_path:
            writers_html += f"""
            <div class="author-block">
                <img src="{avatar_path}" class="author-avatar"/>
                <div class="author-text">
                    <strong>{display_name}</strong><br/>
                    {tag}
                </div>
            </div>
            """
        else:
            writers_html += f"""
            <div class="author-block">
                <div class="author-text">
                    <strong>{display_name}</strong><br/>
                    {tag}
                </div>
            </div>
            """
    word_count = collected_data["word_count"]
    message_count = collected_data["message_count"]
    start_date = collected_data["start_date"]
    end_date = collected_data["end_date"]

    if start_date and end_date:
        timespan = (
            f"{start_date.strftime('%d.%m.%Y')} – {end_date.strftime('%d.%m.%Y')}"
        )
    else:
        timespan = "N/A"

    writers_html = ""
    for display_name, tag, avatar_url in writers.values():
        writers_html += f"""
        <div class="author-block">
            <p><strong>{display_name}</strong><br>{tag}</p>
        </div>
        """

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

    <p><strong>Word Count:</strong> {word_count}</p>
    <p><strong>Total Messages:</strong> {message_count}</p>
    <p><strong>Timespan:</strong> {timespan}</p>
    """
    book.add_item(info_page)

    # Chapters
    chapters = []
    for i, chapter_content in enumerate(collected_data["chapters"], start=1):
        chapter = epub.EpubHtml(
            title=f"Chapter {i}",
            file_name=f"chap_{i}.xhtml",
        )

        chapter_body = ""
        if len(collected_data["chapters"]) > 1:
            chapter_body += f"<h2>CHAPTER {i}</h2>"

        chapter_body += "".join(chapter_content)

        chapter.content = chapter_body
        book.add_item(chapter)
        chapters.append(chapter)

    # Optional Summary Page
    if summary:
        summary_page = epub.EpubHtml(title="Summary", file_name="summary.xhtml")
        summary_page.content = f"""
        <h2>Summary</h2>
        <p>{summary}</p>
        """
        book.add_item(summary_page)
        chapters.append(summary_page)

    # Table of Contents
    book.toc = [title_page, info_page] + chapters

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = ["nav", title_page, info_page] + chapters

    # Save file
    output_filename = f"{title.replace(' ', '_')}.epub"
    output_path = os.path.join("data", output_filename)

    epub.write_epub(output_path, book)

    return output_path


async def collect_channel_content(source_channel, trigger: str = "0"):
    """
    Collects and processes messages from a channel.

    Returns:
        {
            "chapters": [list of chapter HTML strings],
            "writers": {user_id: (display_name, username_tag, avatar_url)},
            "word_count": int,
            "message_count": int,
            "start_date": datetime,
            "end_date": datetime
        }
    """

    chapters = []
    current_chapter = []
    writers = {}

    word_count = 0
    message_count = 0

    chapter_index = 1

    first_timestamp = None
    last_timestamp = None

    async for message in source_channel.history(limit=None, oldest_first=True):
        await asyncio.sleep(0)

        if message.author.bot:
            continue

        content = message.content.strip()

        if not content:
            continue

        # Track timestamps
        if not first_timestamp:
            first_timestamp = message.created_at
        last_timestamp = message.created_at

        # Track writers
        if message.author.id not in writers:
            writers[message.author.id] = (
                message.author.display_name,
                str(message.author),
                message.author.display_avatar.url,
            )

        # Trigger handling (exact match only if trigger provided)
        if trigger and content.strip() == trigger:
            if current_chapter:
                chapters.append(current_chapter)
                current_chapter = []
            continue

        # Convert markdown
        html_text = convert_discord_markdown_to_html(content)

        # Word count
        word_count += len(content.split())
        message_count += 1

        # Add paragraph
        current_chapter.append(f"<p>{html_text}</p>")

    # Append last chapter
    if current_chapter:
        chapters.append(current_chapter)

    # If trigger was 0, flatten into single chapter
    if trigger == "0" and chapters:
        merged = []
        for chapter in chapters:
            merged.extend(chapter)
        chapters = [merged]

    return {
        "chapters": chapters,
        "writers": writers,
        "word_count": word_count,
        "message_count": message_count,
        "start_date": first_timestamp,
        "end_date": last_timestamp,
    }
