"""
Build public ranking messages from /observe word stats.
"""

from datetime import datetime, timezone

import discord


def _rank_colors() -> list[discord.Color]:
    return [
        discord.Color.gold(),
        discord.Color.light_grey(),
        discord.Color.dark_orange(),
        discord.Color.teal(),
        discord.Color.blue(),
    ]


async def _display_name_and_avatar(
    client: discord.Client, guild: discord.Guild, user_id: int
) -> tuple[str, str]:
    member = guild.get_member(user_id)
    if member is not None:
        return member.display_name, member.display_avatar.url
    try:
        m = await guild.fetch_member(user_id)
        return m.display_name, m.display_avatar.url
    except discord.NotFound:
        pass
    except discord.HTTPException:
        pass
    try:
        u = await client.fetch_user(user_id)
        return u.name, u.display_avatar.url
    except discord.HTTPException:
        return f"User {user_id}", ""


async def build_ranking_embeds(
    client: discord.Client,
    guild: discord.Guild,
    entries: list[tuple[int, int]],
) -> list[discord.Embed]:
    """
    Top 5: one embed each with author icon = avatar.
    Ranks 6–10: one embed, text only (name + word count).
    """
    if not entries:
        e = discord.Embed(
            title="Observed channel word ranking",
            description=(
                f"No word stats in **{guild.name}** yet.\n"
                "An admin can run `/observe` on channels to start counting."
            ),
            color=discord.Color.dark_gray(),
            timestamp=datetime.now(timezone.utc),
        )
        return [e]

    header = discord.Embed(
        title="Observed channel word ranking",
        description=(
            f"Top writers in **{guild.name}** (from `/observe` word counts only). "
            "Webhook posts count like story exports."
        ),
        color=discord.Color.dark_teal(),
        timestamp=datetime.now(timezone.utc),
    )
    out: list[discord.Embed] = [header]

    colors = _rank_colors()
    top5 = entries[:5]
    for i, (uid, words) in enumerate(top5, start=1):
        name, avatar_url = await _display_name_and_avatar(client, guild, uid)
        emb = discord.Embed(
            color=colors[i - 1] if i <= len(colors) else discord.Color.dark_teal(),
        )
        if avatar_url:
            emb.set_author(
                name=f"#{i} — {name} — {words:,} words",
                icon_url=avatar_url,
            )
        else:
            emb.set_author(name=f"#{i} — {name} — {words:,} words")
        out.append(emb)

    rest = entries[5:10]
    if rest:
        lines: list[str] = []
        for rank, (uid, words) in enumerate(rest, start=6):
            name, _ = await _display_name_and_avatar(client, guild, uid)
            lines.append(f"**{rank}.** {name} — **{words:,}** words")
        rest_emb = discord.Embed(
            title="Ranks 6–10",
            description="\n".join(lines),
            color=discord.Color.dark_gray(),
        )
        out.append(rest_emb)

    return out


async def post_ranking_to_channel(
    client: discord.Client,
    channel: discord.abc.Messageable,
    guild: discord.Guild,
    entries: list[tuple[int, int]],
) -> None:
    embeds = await build_ranking_embeds(client, guild, entries)
    await channel.send(embeds=embeds)
