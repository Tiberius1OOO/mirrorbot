# DragonCopy Mirror Bot

A Discord bot for **mirroring**, **copying**, **moving**, and **archiving** messages between channels. It is aimed at long-running story servers, archive channels, structured RP, and delayed relays. It can also **export a text channel to an EPUB** for reading or sharing.

---

## Features

### Live relays

- Mirror messages from one channel to another
- Optional delay (spoiler buffers, moderation pacing, or staged publishing)
- Multiple relays per server (**one relay per source channel** — each source maps to a single target)
- Preserves display names and avatars using webhooks named **DragonCopy**
- Splits messages longer than Discord’s 2000-character limit
- Supports attachments
- Counts successful relay sends in per-guild statistics (SQLite)

### Single message copy

- Right-click a message → **Apps → Copy message**
- Pick the target channel
- Preserves author identity and attachments; long text is split safely

### Cut everything from here

- Right-click a message → **Apps → Cut everything from here**
- Pick the target channel

The bot will:

1. Copy the selected message and every **newer** message in that channel (chronological order)
2. Delete the originals in the source channel (where the API allows)

Preserves the same behavior as copy for identity, attachments, and splitting. Requires **Manage Messages** in the source channel for deletes to succeed.

### EPUB export (books)

Administrator slash commands build an **EPUB** from a text channel’s history (non-empty messages; **webhook** messages are kept, ordinary **bot** messages are skipped):


| Command               | Purpose                                                           |
| --------------------- | ----------------------------------------------------------------- |
| `/generate_book`      | “Clean” publication build (no per-post Discord links in the body) |
| `/generate_book_beta` | Same pipeline with **“To Post”** links after each paragraph block |


Shared options:

- **title**, **author** — book metadata  
- **source_channel** — text or announcement **channel**, or a **thread** (including a **forum topic** / side-story post). History is read oldest → newest. Do **not** pick the forum *listing* channel — open the topic and select that **thread**.  
- **upload_channel** — where the generated `.epub` is posted  
- **invite_link** — shown on the info page inside the book  
- **cover_image** (optional) — cover for the EPUB  
- **summary** (optional) — extra page at the end  
- **chapter_file** (optional) — a `**.txt` file** you **upload** as the attachment for this option when you run the command

#### Chapter file (how it works)

Use this when you want **named chapters** in the EPUB instead of one continuous run of posts.

1. **Create a plain text file** (for example `chapters.txt`) on your computer.
2. When you run `/generate_book` or `/generate_book_beta`, set **chapter_file** and **upload that `.txt` file** in Discord (same as attaching any file to a slash command option).
3. The bot reads the file as **UTF-8** text, **one chapter boundary per non-empty line**.

**Line format** (must match exactly — note the commas and straight double quotes around the title):

```text
<message_id>,"Chapter title"
```

- `**message_id**` — the numeric **Discord message ID** (snowflake) of the post that should **start** that chapter. Each message in Discord has its **own** ID, so each new chapter uses a **different** ID: the ID of the **first message** that belongs to that chapter.  
- `**"Chapter title"`** — the title shown in the EPUB for that chapter (in straight double quotes).

**What the bot does with the file:** It loads the channel **oldest → newest** (same order as the story). It walks through messages in that order. Whenever it reaches a message whose ID appears in your file, it **starts a new chapter**: it inserts a chapter heading, uses the **title from that line**, and numbers chapters automatically (**Chapter 1**, **Chapter 2**, …). Content **before** the first listed ID stays in the opening section without a chapter title from the file. Content **after** each listed ID belongs to that chapter until the next listed ID (or the end of the channel).

Example file with **two** chapter breaks (two different message IDs — one per chapter start):

```text
1234567890123456789012,"Opening"
9876543210987654321098,"The Road"
```

#### How to get a message ID (chapter start)

You need the ID of the **exact message** where you want the chapter to begin.

1. In Discord, open **User Settings** → **App Settings** → **Advanced**.
2. Turn **Developer Mode** **on**.
3. Go to the channel you are exporting, find the message that should **start** the chapter.
4. **Right-click** that message (or use the message’s **⋯** menu) and choose **Copy Message ID**.
5. Paste into your `.txt` file as the number before the comma on that chapter’s line.

**Alternative:** **Copy Message Link**, then take the **last number** in the URL — that is the message ID (the URL looks like `https://discord.com/channels/<guild_id>/<channel_id>/<message_id>`).

---

Generated EPUB files are written under `data/<guild_id>/` (existing `.epub` files in that folder are replaced when a new book is generated for the guild).

### Database (SQLite)

Configuration lives in `**data/bot.db`** (not JSON at runtime).

On first startup after upgrading from older JSON configs, files in:

```text
configs/<guild_id>.json
```

are migrated and renamed to:

```text
<guild_id>.migrated.json
```

Tables include **guilds** (error channel), **relays**, and **stats** (e.g. messages copied count).

---

## Commands

All slash commands below require **Administrator**.


| Command               | Description                                                                                                             |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `/setup`              | Initial setup: sets the **current channel** as the bot’s error/diagnostics channel (`/bot_info` posts its embed there). |
| `/start_relay`        | Start a relay: `source`, `target`, `delay_seconds`. Fails if a relay for that **source** already exists.                |
| `/stop_relay`         | Stop the relay for a given **source** channel.                                                                          |
| `/instances`          | List active relays (channel mentions).                                                                                  |
| `/bot_info`           | Send a diagnostic embed to the configured error channel (server, user, uptime, DB row counts, relay list).              |
| `/generate_book`      | Build a clean EPUB from a source channel and upload it to a chosen channel.                                             |
| `/generate_book_beta` | Build a beta EPUB with per-post links to Discord.                                                                       |


Context menu commands (**Copy message**, **Cut everything from here**) also require **Administrator**.

---

## Installation

### Requirements

- **Python 3.10+**
- A Discord bot token with the **Message Content Intent** enabled (the bot reads message content for relays and EPUB export)
- Dependencies listed in `requirements.txt`

### Clone the repository

```bash
git clone https://github.com/Tiberius1OOO/mirrorbot.git
cd mirrorbot
```

### Create a virtual environment

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
pip install -r requirements.txt
```

If you skip this and later **merge or pull** a version that added packages (for example EPUB support), starting `**python bot.py`** will detect missing imports and run `**pip install -r requirements.txt`** automatically once (requires network access). If that fails, run the command above manually in the same environment you use to run the bot.

### Set the bot token

**Linux / macOS**

```bash
export DISCORD_TOKEN_MIRRORBOT="your_token_here"
```

**Windows (PowerShell)**

```powershell
$env:DISCORD_TOKEN_MIRRORBOT="your_token_here"
```

### Run the bot

```bash
python bot.py
```

---

## Required permissions

The bot needs, at minimum:

- View Channel  
- Send Messages  
- Embed Links  
- Manage Webhooks  
- Read Message History  
- Attach Files  
- **Manage Messages** (required for cut/delete operations)

Enable **Server Members Intent** and **Message Content Intent** in the Discord Developer Portal if your bot should see member display names reliably and read message text for relays and EPUB generation.

---

## Known limitations

- Messages older than **14 days** cannot be bulk-deleted (Discord API limitation); cuts may leave some old messages behind.
- Large cut or relay bursts may be slow due to **rate limits**.
- **Delayed relay** messages that have not been sent yet are **lost** if the bot restarts during the wait.
- Each **source** channel can only have **one** active relay at a time. To change target or delay for that source, run `/stop_relay` on the source first, then `/start_relay` again.

---

## License

This project is licensed under the **Creative Commons Attribution–NonCommercial 4.0 (CC BY-NC 4.0)** license.

You may use and modify this bot for **non-commercial** purposes, provided you give appropriate credit to the original author. Commercial use requires explicit permission.

Full license: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode)