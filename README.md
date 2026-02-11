# DragonCopy Mirror Bot

A lightweight Discord bot for copying and relaying messages between channels.
Designed for long-term story servers, archive channels, and delayed relays.

---

## Features

### Channel copy

* Copy an entire channel into another one
* Preserves usernames and avatars using webhooks
* Automatically splits messages longer than Discord’s 2000-character limit
* Supports attachments

### Single message copy

* Right-click any message
* Select **Copy message**
* Choose the target channel

### Live relays

* Mirror messages from one channel to another
* Optional delay (for spoiler buffers or moderation)
* Multiple relays per server

### Per-server configuration

* Each server gets its own config file
* No overlap between communities

### Error logging

* Dedicated error channel per server
* Admin-only control

### Basic stats

* Tracks how many messages were copied

---

## Commands

All commands are **administrator-only**.

### Setup

```
/setup
```

Initial setup. Select the channel where the bot should send error messages.

---

### Copy a full channel

```
/copy_channel
```

Opens a UI:

1. Choose source channel
2. Choose target channel
3. Start copying

---

### Start a live relay

```
/start_relay source: target: delay_seconds:
```

Example:

```
/start_relay source:#rp target:#archive delay_seconds:3600
```

---

### Stop a relay

```
/stop_relay source:
```

---

### Show active relays

```
/instances
```

---

### Bot diagnostics

```
/bot_info
```

---

### Test error channel

```
/test_error
```

---

## Message context command

Right-click a message:

```
Apps → Copy message
```

Select the destination channel and the bot will mirror it.

---

## Installation

### Requirements

* Python 3.10+
* Discord bot token
* `discord.py`

---

### Clone repository

```bash
git clone https://github.com/Tiberius1OOO/mirrorbot.git
cd mirrorbot
```

---

### Create virtual environment

**Linux/macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows**

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

### Set the bot token

**Linux/macOS**

```bash
export DISCORD_TOKEN="your_token_here"
```

**Windows**

```powershell
$env:DISCORD_TOKEN="your_token_here"
```

---

### Run the bot

```bash
python bot.py
```

---

## Configuration

Each server gets its own config file:

```
configs/<guild_id>.json
```

Example structure:

```json
{
  "error_channel": 1234567890,
  "relays": [],
  "stats": {
    "messages_copied": 0
  }
}
```

---

## Required Permissions

The bot needs:

* Send Messages
* Manage Webhooks
* Read Message History
* Attach Files

---

## Known Limitations

* Pending relay messages are lost if the bot restarts during the delay
* Very large channel copies may take hours due to rate limits
* Uses file-based config instead of a database by design

---

## Purpose

Originally built for collaborative sci-fi writing servers to manage mirrored RP channels, spoiler buffers, and archive copies.
Designed to be simple, transparent, and easy to host on low-power hardware like a Raspberry Pi.
