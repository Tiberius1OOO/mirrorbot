# DragonCopy Mirror Bot

A lightweight Discord bot for copying, relaying, cutting, and managing messages between channels.  
Designed for long-term story servers, archive channels, structured RP environments, and delayed relays.

---

## Features

### Live relays

* Mirror messages from one channel to another
* Optional delay (for spoiler buffers or moderation)
* Multiple relays per server
* Preserves usernames and avatars using webhooks
* Automatically splits messages longer than Discord’s 2000-character limit
* Supports attachments

---

### Single message copy

* Right-click any message
* Select **Apps → Copy message**
* Choose the target channel
* Preserves author identity and attachments
* Automatically handles long messages

---

### Cut everything from here

* Right-click any message
* Select **Apps → Cut everything from here**
* Choose a target channel

The bot will:

1. Copy the selected message  
2. Copy every message after it  
3. Delete the original messages from the source channel  

Preserves:

* Author identity
* Avatars
* Attachments
* Message order
* Automatic long-message splitting

Requires:

* **Manage Messages** permission in the source channel

---

### Database (v1.1 Redesign)

DragonCopy now uses a **SQLite database backend** instead of JSON configuration files.

On first startup after upgrading from v1.0, old config files:

    configs/<guild_id>.json

are automatically migrated and renamed to:

    <guild_id>.migrated.json

After migration, the bot runs fully on the database.

Database file location:

    data/bot.db

Tables:

* guilds
* relays
* stats

---

## Commands

All commands are **administrator-only**.

### Setup

    /setup

Initial setup. Select the channel where the bot should send error messages.

---

### Start a live relay

    /start_relay source: target: delay_seconds:

Example:

    /start_relay source:#rp target:#archive delay_seconds:3600

---

### Stop a relay

    /stop_relay source:

---

### Show active relays

    /instances

---

### Bot diagnostics

    /bot_info

Posts a structured embed into the configured error channel including:

* Command user
* Server name and ID
* Member count
* Bot start time
* Uptime
* Active relay count
* Database entry counts

---

## Installation

### Requirements

* Python 3.10+
* Discord bot token
* discord.py

---

### Clone repository

```bash
git clone https://github.com/Tiberius1OOO/mirrorbot.git
cd mirrorbot
```

---

### Create virtual environment

Linux / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

---

### Install dependencies

```bash
pip install discord.py
```

---

### Set bot token

Linux / macOS:

```bash
export DISCORD_TOKEN_MIRRORBOT="your_token_here"
```

Windows (PowerShell):

```powershell
$env:DISCORD_TOKEN_MIRRORBOT="your_token_here"
```

---

### Run the bot

```bash
python bot.py
```

---

## Required Permissions

The bot needs:

* View Channel
* Send Messages
* Embed Links
* Manage Webhooks
* Read Message History
* Attach Files
* Manage Messages (required for cut operations)

---

## Known Limitations

* Messages older than 14 days cannot be bulk-deleted (Discord API limitation)
* Large cut operations may take time due to rate limits
* Pending delayed relay messages are lost if the bot restarts during the delay

---

## License

This project is licensed under the  
**Creative Commons Attribution–NonCommercial 4.0 (CC BY-NC 4.0)** license.

You are free to use and modify this bot for non-commercial purposes,  
but you must give proper credit to the original author.

Commercial use requires explicit permission.
