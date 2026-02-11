DragonCopy Mirror Bot

A lightweight Discord bot for copying and relaying messages between channels.
Originally built for long-term story development servers where content needs to be mirrored, delayed, or archived without manual reposting.

The bot focuses on reliability, simple setup, and per-server configuration.

Features

Channel copy

Copy an entire channel into another one

Preserves usernames and avatars using webhooks

Automatically splits messages longer than Discord’s 2000-character limit

Works with attachments

Single message copy

Right-click any message

Select Copy message

Choose the target channel

Live relays

Mirror messages from one channel to another

Optional delay (for spoiler buffers, moderation, etc.)

Multiple relays per server

Per-server configuration

Each server gets its own config file

No overlap between different communities

Error logging

Dedicated error channel per server

Admin-only control

Basic stats

Tracks how many messages were copied

Commands

All commands are administrator-only.

Setup
/setup


Initial setup.
Select the channel where the bot should send error messages.

Copy a full channel
/copy_channel


Opens a channel selector UI:

Choose source channel

Choose target channel

Start copying

Start a live relay
/start_relay source:<channel> target:<channel> delay_seconds:<number>


Creates a live relay from one channel to another.

Example:

/start_relay source:#rp target:#archive delay_seconds:3600

Stop a relay
/stop_relay source:<channel>


Stops the relay for the selected source channel.

Show active relays
/instances


Displays all configured relays for the server.

Bot diagnostics
/bot_info


Sends a diagnostic report to the configured error channel.

Test error channel
/test_error


Sends a test message to confirm the error system works.

Message context command

Right-click a message:

Apps → Copy message


Select the destination channel and the bot will mirror it.

Installation
Requirements

Python 3.10+

A Discord bot token

discord.py installed

1. Clone the repository
git clone https://github.com/yourname/mirrorbot.git
cd mirrorbot

2. Create virtual environment
python3 -m venv venv
source venv/bin/activate


On Windows:

venv\Scripts\activate

3. Install dependencies
pip install discord.py

4. Set the bot token

Linux/macOS:

export DISCORD_TOKEN="your_token_here"


Windows:

set DISCORD_TOKEN=your_token_here

5. Run the bot
python bot.py

Raspberry Pi (quick setup)

Inside the bot folder:

python3 -m venv venv
source venv/bin/activate
pip install discord.py
python bot.py


Then create a systemd service for auto-start.

Configuration

Each server gets its own config file:

configs/<guild_id>.json


Example structure:

{
    "error_channel": 1234567890,
    "relays": [],
    "stats": {
        "messages_copied": 0
    }
}

Permissions required

The bot needs:

Send Messages

Manage Webhooks

Read Message History

Attach Files

Known limitations

Pending relay messages are lost if the bot restarts during the delay.

Extremely large channel copies may take hours due to Discord rate limits.

No database is used; everything is file-based by design.

Purpose

This bot was built for a collaborative sci-fi writing community to manage mirrored RP channels, spoiler buffers, and archival copies.
It is intentionally simple, transparent, and easy to host on low-power hardware like a Raspberry Pi.
