def split_message(content, limit=2000):
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
