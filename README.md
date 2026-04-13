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

### Observed-channel word stats and leaderboard

- Admins add channels or forum topics with **`/observe`**; the bot counts words there (relays do **not** change these totals).
- **`/bot_info`** shows each member their own stats (everyone) and extra diagnostics for admins.
- **`/ranking`** (admin-only to invoke) posts a **public** top-**10** leaderboard in the channel: **1–5** with avatars, **6–10** as names and word counts.
- **`/ranking_setup`** (admin, ephemeral) can turn on **scheduled** posts of that leaderboard to a chosen channel, on a **12** or **24** hour UTC schedule.

### EPUB export (books)

Administrator slash commands build an **EPUB** from message history (non-empty messages; **webhook** messages are kept, ordinary **bot** messages are skipped).

| Command | Purpose |
|--------|---------|
| `/generate_book` | Clean publication build (no per-post Discord links in the story body). |
| `/generate_book_beta` | Same export, but each in-world post can include a **“To Post”** link back to Discord. |

#### How to run a book command

1. Type `/generate_book` or `/generate_book_beta` in a channel where you can use the bot (any channel is fine; it does not change what you export).
2. Discord shows a form with **options** (fields). Fill in the **required** ones first, then add **optional** ones if you want them.
3. **Required options** must all be set before you can submit. **Optional** options can be left empty or not attached.
4. Submit the command. The bot reads the **source**, builds the EPUB, and posts the finished file as an attachment in **upload_channel** (and confirms to you ephemerally).

#### Required options (both commands)

These always appear and must be filled:

| Option | What to enter |
|--------|----------------|
| **title** | Book title as it should appear on the cover and title page. |
| **author** | Author line for the EPUB metadata (can be a pen name or “Various”). |
| **source_channel** | Where the story lives: a **text** or **announcement** channel, or a **thread** (e.g. a **forum topic** / side-story post). The bot reads full history **oldest → newest**. **Do not** select the forum *listing* channel — open the topic and pick that **thread**. |
| **upload_channel** | Where the bot should **post the `.epub` file** when it is done (any text channel or thread the bot can send files in). |

#### Optional options (both commands)

You can skip any of these; the EPUB still generates.

| Option | What it does |
|--------|----------------|
| **invite_link** | If you paste a **permanent server invite URL**, it is shown on the EPUB **info** page under “Generated from”. Leave **empty** to omit the link (only the server name appears). |
| **cover_image** | Attach an image file to use as the **cover**. |
| **summary** | Short text; if set, the EPUB gets an extra **Summary** page at the end. |
| **chapter_file** | Attach a `.txt` file that defines **chapter titles** and **breaks** (see below). Without it, the book is one continuous flow of posts (still split into EPUB chapters internally only if you use a chapter file). |

#### Chapter file (optional)

Use this when you want **named chapters** in the EPUB instead of one continuous run of posts.

1. **Create a plain text file** (for example `chapters.txt`) on your computer.
2. When you run `/generate_book` or `/generate_book_beta`, set **chapter_file** and **upload that `.txt` file** in Discord (same as attaching any file to a slash command option).
3. The bot reads the file as **UTF-8** text, **one chapter boundary per non-empty line**.

**Line format** (must match exactly — note the commas and straight double quotes around the title):

```text
<message_id>,"Chapter title"
```

- **message_id** — the numeric **Discord message ID** (snowflake) of the post that should **start** that chapter. Each message has its **own** ID, so each new chapter line uses a **different** ID (the first message of that chapter).  
- **"Chapter title"** — the title for that chapter in straight double quotes.

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

Configuration lives in `data/bot.db` (not JSON at runtime).

On first startup after upgrading from older JSON configs, files in:

```text
configs/<guild_id>.json
```

are migrated and renamed to:

```text
<guild_id>.migrated.json
```

Tables include **guilds** (error channel), **relays**, **stats** (messages mirrored counter), **relay_word_stats** (per-member word totals from **observed** channels), **observed_channels** (which channels/threads count toward stats), **channel_word_watermarks** (so re-adding `/observe` after `/unobserve` only scans **new** history and does not double-count old messages), and **ranking_autopost** (optional schedule for automatic `/ranking`-style posts in a channel).

On upgrade, `CREATE TABLE IF NOT EXISTS` runs automatically — your existing `bot.db` is extended in place; no manual migration file is required.

---

## Commands

Most configuration commands require **Administrator**. **`/bot_info` is available to everyone** in the server.

In supported Discord clients, commands that require **Administrator** are **hidden** from members who do not have that permission (the bot still checks permissions when a command runs). **`/bot_info`** stays visible to everyone.

| Command | Who can use it | Description |
|--------|----------------|-------------|
| `/setup` | Administrator | Sets the **current channel** as the bot’s error/diagnostics channel (legacy logging; not required for `/bot_info`). |
| `/start_relay` | Administrator | Start a relay: `source`, `target`, `delay_seconds`. Fails if a relay for that **source** already exists. |
| `/stop_relay` | Administrator | Stop the relay for a given **source** channel. |
| `/instances` | Administrator | List active relays (channel mentions). |
| `/observe` | Administrator | Pick a **text** channel, **announcement** channel, or **forum topic thread**. The bot **scans full message history** once (initial word counts), then **keeps counting** new messages until `/unobserve`. Nothing is tracked until an admin runs this. |
| `/unobserve` | Administrator | Stop counting in that channel/thread. **Totals stay**; a **watermark** remembers how far history was scanned so `/observe` again only adds **new** messages. |
| `/observing` | Administrator | List all channels/threads currently observed. |
| `/ranking` | Administrator | Posts the **top 10** writers by observed-channel word count **in the channel** (public message): ranks **1–5** use avatars; **6–10** are names and counts only. |
| `/ranking_setup` | Administrator | Configure **automatic** ranking posts (reply is **ephemeral**): target channel/thread, **12** or **24** hour cadence, first post time **`HH:MM` in UTC**, or disable autopost. Discord has no per-server timezone — convert local time to UTC. **12h** posts at that UTC time and again 12 hours later; **24h** once per day at that clock time. |
| `/bot_info` | **Everyone** | **Personal card:** avatar, join date, **words** from **observed** channels, **rank**, server total. **Administrators** also get diagnostics: relays, **observed list**, leaderboard, etc. **Ephemeral**. |
| `/generate_book` | Administrator | Build a clean EPUB from a source channel and upload it to a chosen channel. |
| `/generate_book_beta` | Administrator | Build a beta EPUB with per-post links to Discord. |

### Word tracking and ranking (`/observe`)

- **Relays do not affect stats.** Only channels (or forum topics) an admin adds with **`/observe`** are counted.
- On **`/observe`**, the bot runs an **initial history scan** (same rules as EPUBs: normal **bot** posts are skipped, **webhook** posts count), then **live** messages in that channel add words until **`/unobserve`**.
- **Re-observing** after **`/unobserve`** only processes messages **after** the saved watermark, so old text is **not** double-counted.
- Counts use whitespace-split words (like EPUB export). Only traffic **while the bot is running** is counted for live messages; the backlog scan runs at `/observe` time.
- Rankings are per-server. If nobody has used **`/observe`** yet, there is no leaderboard.
- **`/ranking`** (admin-only to run, **public** result) and optional **`/ranking_setup`** autoposts use the same leaderboard data as **`/bot_info`**.
- If you used an **older** build that counted **relay sources** automatically, those totals may still be in the database; from now on, **only `/observe` channels** gain new words.

Context menu commands (**Copy message**, **Cut everything from here**) require **Administrator** and use the same visibility rules as other admin commands.

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