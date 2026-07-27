# DragonCopy Mirror Bot

Discord bot for **mirroring**, **copying**, **moving**, and **archiving** channel messages. Built for story servers, archives, structured RP, and delayed relays — with EPUB and plain-text export.

---

## Raspberry Pi (recommended)

One script handles install, start, stop, update, and boot auto-start. It soft-stops any old bot process, removes stray auto-start entries (`mirrorbot.service`, crontabs, etc.), then installs a single clean `dragoncopy` systemd service. Removed units are copied first to `/etc/systemd/system/*.dragoncopy.bak.*` so an old embedded token is not lost.

```bash
git clone https://github.com/Tiberius1OOO/mirrorbot.git
cd mirrorbot
chmod +x dragoncopy
./dragoncopy install    # asks for the bot token, then sets everything up
```

`install` prompts for your Discord bot token (hidden input, confirm twice) and stores it **only** inside `/etc/systemd/system/dragoncopy.service` (mode `600`) — the same place your old `mirrorbot.service` kept it. No `/etc/environment` edits and no extra token files.

```bash
./dragoncopy stop
./dragoncopy start
./dragoncopy update     # git pull + deps + restart (keeps token)
./dragoncopy token      # change token later
./dragoncopy status
./dragoncopy restart
./dragoncopy uninstall  # remove service; backs up the unit first
```

`update` pulls `main`, refreshes dependencies, and starts the bot again.

---

## Features

| Area | What it does |
|------|----------------|
| **Live relays** | Mirror a source channel to a target (optional delay). One relay per source. Webhooks named **DragonCopy** keep display name + avatar. Attachments and long-message splits supported. |
| **Copy message** | Right-click → **Apps → Copy message** → pick target. |
| **Copy from here** | Right-click → **Apps → Copy everything from here** → copies that message and every newer one. Originals stay. |
| **Cut from here** | Same range as copy-from-here, then deletes originals (needs **Manage Messages**). |
| **Word stats** | `/observe` channels; `/bot_info`, `/ranking`, optional `/ranking_setup` autopost. |
| **Exports** | `/export_flowtext` (plain `.txt`) and `/generate_book` / `/generate_book_beta` (EPUB). |
| **Notes** | `/notes open` and `/notes info` — shared per-channel notepad. |

Runtime state lives in SQLite at `data/bot.db` (created automatically). Older JSON configs under `configs/` are migrated on first start.

---

## Slash commands

Most config commands need **Administrator**. `/bot_info` is available to everyone.

Discord shows the full slash list to members by default. Hide commands per role under **Server Settings → Integrations → your bot**.

| Command | Who | Description |
|---------|-----|-------------|
| `/setup` | Admin | Set current channel as error/diagnostics channel. |
| `/start_relay` | Admin | Start relay: `source`, `target`, `delay_seconds`. |
| `/stop_relay` | Admin | Stop relay for a source channel. |
| `/instances` | Admin | List active relays. |
| `/observe` | Admin | Count words in a text/announcement channel or forum topic. |
| `/unobserve` | Admin | Stop counting (totals kept; watermark avoids double-count). |
| `/observing` | Admin | List observed channels. |
| `/ranking` | Admin | Public top-10 word leaderboard. |
| `/ranking_setup` | Admin | Schedule ranking posts (12h/24h UTC). |
| `/bot_info` | Everyone | Personal stats; admins also see diagnostics. Ephemeral. |
| `/generate_book` | Admin | Clean EPUB export. |
| `/generate_book_beta` | Admin | EPUB with per-post Discord links. |
| `/export_flowtext` | Admin | Plain-text channel export. |
| `/notes open` | — | Shared channel notepad. |
| `/notes info` | — | Notes help / limits. |

Context menus (**Copy message**, **Copy everything from here**, **Cut everything from here**) also require **Administrator**.

---

## EPUB export

Required options: **title**, **author**, **source_channel**, **upload_channel**.

Optional: **invite_link**, **cover_image**, **summary**, **chapter_file**.

**source_channel** may be a text/announcement channel or a **thread** (forum topic). Do not pick the forum listing channel.

### Chapter file (optional)

Attach a UTF-8 `.txt` with one boundary per line:

```text
<message_id>,"Chapter title"
```

Enable **Developer Mode** in Discord → right-click a message → **Copy Message ID** (or take the last number from **Copy Message Link**).

Webhook posts are kept; ordinary bot posts are skipped. Files are written under `data/<guild_id>/`.

---

## Bot permissions

Minimum: View Channel, Send Messages, Embed Links, Manage Webhooks, Read Message History, Attach Files, and **Manage Messages** (for cut).

In the Developer Portal, enable **Server Members Intent** and **Message Content Intent**.

Members who use slash commands need **Use Application Commands** in that channel.

---

## Manual install (without the script)

```bash
git clone https://github.com/Tiberius1OOO/mirrorbot.git
cd mirrorbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DISCORD_TOKEN_MIRRORBOT="your_token_here"
python bot.py
```

If you pull a release that adds packages and skip `pip install`, `python bot.py` will try to install from `requirements.txt` once automatically.

---

## Known limitations

- Very old messages may not delete during cut (Discord API limits); the bot deletes one-by-one, not bulk.
- Large copy/cut/relay bursts are paced for rate limits.
- Delayed relay messages still waiting are lost if the process restarts mid-delay.
- One active relay per source channel — `/stop_relay` before changing target or delay.
- Huge text exports can hit Discord’s attachment size limit (~25 MB for bots).

---

## License

**Creative Commons Attribution–NonCommercial 4.0 (CC BY-NC 4.0)**.

Non-commercial use and modification with credit. Commercial use needs explicit permission.

Full text: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode)
