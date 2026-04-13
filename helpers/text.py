"""
Text Utilities
==============

Provides helper functions for handling message content.

Primary responsibility:
• Splitting long messages into Discord-safe chunks

Why this exists
---------------
Discord enforces a strict message length limit
(currently 2000 characters per message).

When copying or relaying messages, content may exceed
this limit. This module ensures messages are split
cleanly without breaking words or sentences when possible.

Splitting Strategy
------------------
The algorithm attempts to split in this order:

1. End of sentence:
   • ". "
   • "! "
   • "? "

2. Line break:
   • "\\n"

3. Word boundary:
   • Space character

4. Hard split:
   • Exactly at the character limit

This keeps messages readable while remaining safe
for Discord’s API.
"""


def count_words(content: str) -> int:
    """
    Counts whitespace-separated words in message text (same idea as EPUB export).
    Empty or whitespace-only strings return 0.
    """
    if not content or not content.strip():
        return 0
    return len(content.strip().split())


def split_message(content, limit=2000):
    """
    Splits a message into chunks that fit within
    Discord’s message length limit.

    The function attempts to split at natural
    boundaries (sentence endings, line breaks,
    or spaces) before falling back to a hard split.

    Args:
        content (str):
            The message content to split.

        limit (int, optional):
            Maximum characters per message.
            Default is 2000 (Discord limit).

    Returns:
        list[str]:
            A list of message parts, each within
            the specified length limit.
    """
    parts = []

    while len(content) > limit:
        chunk = content[:limit]

        split_at = max(chunk.rfind(". "), chunk.rfind("! "), chunk.rfind("? "))

        if split_at == -1:
            split_at = chunk.rfind("\n")
        if split_at == -1:
            split_at = chunk.rfind(" ")
        if split_at == -1:
            split_at = limit
        else:
            split_at += 1

        parts.append(content[:split_at].strip())
        content = content[split_at:].strip()

    if content:
        parts.append(content)

    return parts
