import discord
from discord import app_commands
import json
import os
import asyncio

TOKEN = "*API Token here"

CONFIG_FOLDER = "configs"

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# ---------- Helper functions ----------


def get_config_path(guild_id: int):
    return os.path.join(CONFIG_FOLDER, f"{guild_id}.json")


def save_config(guild_id: int, data: dict):
    os.makedirs(CONFIG_FOLDER, exist_ok=True)
    with open(get_config_path(guild_id), "w") as f:
        json.dump(data, f, indent=4)


def load_and_prepare_config(guild_id: int):
    path = get_config_path(guild_id)

    if not os.path.exists(path):
        return None

    with open(path, "r") as f:
        config = json.load(f)

    changed = False

    if "relays" not in config:
        config["relays"] = []
        changed = True

    if "stats" not in config:
        config["stats"] = {"messages_copied": 0}
        changed = True

    if "messages_copied" not in config["stats"]:
        config["stats"]["messages_copied"] = 0
        changed = True

    if changed:
        save_config(guild_id, config)

    return config


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


async def send_error(guild: discord.Guild, message: str):
    print(f"[ERROR] Guild: {guild.id if guild else 'Unknown'} | {message}")

    if guild is None:
        return

    config = load_and_prepare_config(guild.id)
    if not config:
        return

    error_channel_id = config.get("error_channel")
    if not error_channel_id:
        return

    channel = guild.get_channel(error_channel_id)
    if not channel:
        return

    try:
        await channel.send(f"⚠️ Bot Error:\n{message}")
    except Exception as e:
        print(f"[ERROR] Failed to send error to channel: {e}")


async def get_or_create_webhook(channel: discord.TextChannel):
    webhooks = await channel.webhooks()
    for hook in webhooks:
        if hook.name == "DragonCopy":
            return hook
    return await channel.create_webhook(name="DragonCopy")


# ---------- Setup UI ----------


class ErrorChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, guild_id: int):
        super().__init__(
            placeholder="Select error channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]

        config = {
            "error_channel": channel.id,
            "relays": [],
            "stats": {"messages_copied": 0},
        }

        save_config(self.guild_id, config)

        await interaction.response.send_message(
            f"Setup complete. Error channel set to {channel.mention}", ephemeral=True
        )


class SetupView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.add_item(ErrorChannelSelect(guild_id))


# ---------- Commands ----------


@tree.command(name="stop_relay", description="Stop a relay by source channel")
@app_commands.checks.has_permissions(administrator=True)
async def stop_relay(interaction: discord.Interaction, source: discord.TextChannel):
    guild_id = interaction.guild.id

    config = load_and_prepare_config(guild_id)
    if not config:
        await interaction.response.send_message("Setup not completed.", ephemeral=True)
        return

    relays = config.get("relays", [])
    new_relays = [r for r in relays if r["source"] != source.id]

    config["relays"] = new_relays
    save_config(guild_id, config)

    await interaction.response.send_message(
        f"Relay for {source.mention} stopped.", ephemeral=True
    )


@tree.command(name="start_relay", description="Start a live relay between channels")
@app_commands.checks.has_permissions(administrator=True)
async def start_relay(
    interaction: discord.Interaction,
    source: discord.TextChannel,
    target: discord.TextChannel,
    delay_seconds: int,
):
    guild_id = interaction.guild.id

    config = load_and_prepare_config(guild_id)
    if not config:
        await interaction.response.send_message(
            "Setup not completed. Please run /setup first.", ephemeral=True
        )
        return

    relay = {"source": source.id, "target": target.id, "delay": delay_seconds}

    config["relays"].append(relay)
    save_config(guild_id, config)

    await interaction.response.send_message(
        f"Relay started:\n{source.mention} → {target.mention}\nDelay: {delay_seconds}s",
        ephemeral=True,
    )


@tree.command(name="copy_channel", description="Copy a full channel into another")
@app_commands.checks.has_permissions(administrator=True)
async def copy_channel(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    config = load_and_prepare_config(guild_id)
    if not config:
        await interaction.response.send_message(
            "Setup not completed. Please run /setup first.", ephemeral=True
        )
        return

    view = ChannelCopyView(interaction.guild)

    await interaction.response.send_message(
        "Select source and target channels, then press Start copying.",
        view=view,
        ephemeral=True,
    )


@tree.command(name="setup", description="Initial bot setup")
@app_commands.checks.has_permissions(administrator=True)
async def setup_command(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    if os.path.exists(get_config_path(guild_id)):
        await interaction.response.send_message(
            "Setup already completed for this server.", ephemeral=True
        )
        return

    view = SetupView(guild_id)

    await interaction.response.send_message(
        "Good evening. Thanks for using DragonCopy Mirror Bot.\n"
        "Please select a channel where I can send error messages.",
        view=view,
        ephemeral=True,
    )


@tree.command(name="test_error", description="Send a test message to the error channel")
@app_commands.checks.has_permissions(administrator=True)
async def test_error(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    config = load_and_prepare_config(guild_id)
    if not config:
        await interaction.response.send_message(
            "Setup not completed. Please run /setup first.", ephemeral=True
        )
        return

    error_channel_id = config["error_channel"]
    channel = interaction.guild.get_channel(error_channel_id)

    if not channel:
        await interaction.response.send_message(
            "Error channel not found. Please run /setup again.", ephemeral=True
        )
        return

    await channel.send(
        f"Test message from {client.user.mention}: error system is working."
    )

    await interaction.response.send_message(
        "Test message sent to the error channel.", ephemeral=True
    )


@tree.command(
    name="bot_info", description="Send bot diagnostic info to the error channel"
)
@app_commands.checks.has_permissions(administrator=True)
async def bot_info(interaction: discord.Interaction):
    guild = interaction.guild
    guild_id = guild.id
    user = interaction.user

    config = load_and_prepare_config(guild_id)
    if not config:
        await interaction.response.send_message(
            "Setup not completed. Please run /setup first.", ephemeral=True
        )
        return

    relays = config.get("relays", [])

    # Build relay info
    if relays:
        relay_lines = []
        for r in relays:
            source = guild.get_channel(r["source"])
            target = guild.get_channel(r["target"])

            source_name = source.name if source else f"Unknown({r['source']})"
            target_name = target.name if target else f"Unknown({r['target']})"

            relay_lines.append(f"{source_name} → {target_name} | Delay: {r['delay']}s")

        relay_info = "\n".join(relay_lines)
    else:
        relay_info = "No active relays"

    total_copied = config["stats"]["messages_copied"]

    info_text = (
        "**Bot Info Dump**\n"
        f"- Relay Instances:\n{relay_info}\n\n"
        f"- Server ID:\n{guild_id}\n\n"
        f"- Command User:\n{user.id} - {user}\n\n"
        f"- Stats:\n"
        f"Messages copied total: {total_copied}"
    )

    error_channel_id = config["error_channel"]
    channel = guild.get_channel(error_channel_id)

    if not channel:
        await interaction.response.send_message(
            "Error channel not found.", ephemeral=True
        )
        return

    await channel.send(info_text)

    await interaction.response.send_message(
        "Bot info sent to error channel.", ephemeral=True
    )


@tree.command(name="instances", description="Show active relay instances")
@app_commands.checks.has_permissions(administrator=True)
async def instances(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    config = load_and_prepare_config(guild_id)
    if not config:
        await interaction.response.send_message(
            "Setup not completed. Please run /setup first.", ephemeral=True
        )
        return

    relays = config.get("relays", [])

    if not relays:
        await interaction.response.send_message(
            "No active relay instances.", ephemeral=True
        )
        return

    message_lines = [f"Active relays: {len(relays)}\n"]

    for i, relay in enumerate(relays, start=1):
        source = interaction.guild.get_channel(relay["source"])
        target = interaction.guild.get_channel(relay["target"])
        delay = relay["delay"]

        source_name = source.mention if source else f"Unknown({relay['source']})"
        target_name = target.mention if target else f"Unknown({relay['target']})"

        message_lines.append(
            f"{i}) {source_name} → {target_name}\nDelay: {delay} seconds\n"
        )

    await interaction.response.send_message("\n".join(message_lines), ephemeral=True)


# ---------- Copy UI ----------


class CopyChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, message: discord.Message):
        super().__init__(
            placeholder="Select target channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.source_message = message

    async def callback(self, interaction: discord.Interaction):
        selected_channel = self.values[0]
        guild = interaction.guild

        target_channel = guild.get_channel(selected_channel.id)

        try:
            webhook = await get_or_create_webhook(target_channel)

            username = self.source_message.author.display_name
            avatar = self.source_message.author.display_avatar.url
            content = self.source_message.content

            files = []
            attachments = self.source_message.attachments or []
            for attachment in attachments:
                file = await attachment.to_file()
                files.append(file)
            if files:
                await webhook.send(
                    content=content, username=username, avatar_url=avatar, files=files
                )
            else:
                await webhook.send(
                    content=content, username=username, avatar_url=avatar
                )

            await interaction.response.send_message(
                f"Message copied to {target_channel.mention}", ephemeral=True
            )

        except Exception as e:
            await send_error(guild, str(e))
            await interaction.response.send_message(
                "Failed to copy message. Error reported.", ephemeral=True
            )


class CopyView(discord.ui.View):
    def __init__(self, message: discord.Message):
        super().__init__(timeout=60)
        self.add_item(CopyChannelSelect(message))


# ---------- Message context command ----------


@tree.context_menu(name="Copy message")
@app_commands.checks.has_permissions(administrator=True)
async def copy_message_context(
    interaction: discord.Interaction, message: discord.Message
):
    guild_id = interaction.guild.id
    config = load_and_prepare_config(guild_id)

    if not config:
        await interaction.response.send_message(
            "Setup not completed. Please run /setup first.", ephemeral=True
        )
        return

    view = CopyView(message)

    await interaction.response.send_message(
        "Select a target channel:", view=view, ephemeral=True
    )


# ---------- Channel Copy UI ----------


class ChannelCopyView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=120)
        self.guild = guild
        self.source = None
        self.target = None

        self.add_item(SourceChannelSelect(self))
        self.add_item(TargetChannelSelect(self))
        self.add_item(StartCopyButton(self))


class SourceChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view):
        super().__init__(
            placeholder="Select source channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.source = self.values[0]
        await interaction.response.send_message(
            f"Source set to {self.values[0].mention}", ephemeral=True
        )


class TargetChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, parent_view):
        super().__init__(
            placeholder="Select target channel",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.target = self.values[0]
        await interaction.response.send_message(
            f"Target set to {self.values[0].mention}", ephemeral=True
        )


class StartCopyButton(discord.ui.Button):
    def __init__(self, parent_view):
        super().__init__(label="Start copying", style=discord.ButtonStyle.green)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild

        if not self.parent_view.source or not self.parent_view.target:
            await interaction.response.send_message(
                "Please select both source and target channels.", ephemeral=True
            )
            return

        source_channel = guild.get_channel(self.parent_view.source.id)
        target_channel = guild.get_channel(self.parent_view.target.id)

        await interaction.response.send_message(
            f"Starting channel copy from {source_channel.mention} to {target_channel.mention}...",
            ephemeral=True,
        )

        try:
            webhook = await get_or_create_webhook(target_channel)
            config = load_and_prepare_config(guild.id)
            copied_count = 0

            # Fetch messages oldest → newest
            async for msg in source_channel.history(limit=None, oldest_first=True):
                # Correct nickname handling
                if isinstance(msg.author, discord.Member):
                    username = msg.author.display_name
                else:
                    username = msg.author.name

                avatar = msg.author.display_avatar.url
                content = msg.content or ""

                files = []
                attachments = msg.attachments or []

                for attachment in attachments:
                    file = await attachment.to_file()
                    files.append(file)

                # Skip completely empty messages
                if not content and not files:
                    continue

                parts = split_message(content) if content else [""]

                for i, part in enumerate(parts):
                    if i == 0 and files:
                        await webhook.send(
                            content=part,
                            username=username,
                            avatar_url=avatar,
                            files=files,
                        )
                    else:
                        await webhook.send(
                            content=part, username=username, avatar_url=avatar
                        )

                    copied_count += 1
                    await asyncio.sleep(1.0)
            config["stats"]["messages_copied"] += copied_count
            save_config(guild.id, config)

        except Exception as e:
            await send_error(guild, str(e))


# ---------- Events ----------


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    guild = message.guild
    if not guild:
        return

    config = load_and_prepare_config(guild.id)
    if not config:
        return

    relays = config.get("relays", [])

    for relay in relays:
        if message.channel.id != relay["source"]:
            continue

        target_channel = guild.get_channel(relay["target"])
        if not target_channel:
            continue

        delay = relay["delay"]

        async def delayed_send(msg, target, delay_seconds):
            await asyncio.sleep(delay_seconds)

            try:
                webhook = await get_or_create_webhook(target)
                config = load_and_prepare_config(guild.id)
                copied_count = 0

                if isinstance(msg.author, discord.Member):
                    username = msg.author.display_name
                else:
                    username = msg.author.name

                avatar = msg.author.display_avatar.url
                content = msg.content or ""

                files = []
                for attachment in msg.attachments:
                    file = await attachment.to_file()
                    files.append(file)

                if not content and not files:
                    return

                parts = split_message(content) if content else [""]

                for i, part in enumerate(parts):
                    if i == 0 and files:
                        await webhook.send(
                            content=part,
                            username=username,
                            avatar_url=avatar,
                            files=files,
                        )
                    else:
                        await webhook.send(
                            content=part, username=username, avatar_url=avatar
                        )

                    copied_count += 1
                    await asyncio.sleep(1.0)
                config["stats"]["messages_copied"] += copied_count
                save_config(guild.id, config)

            except Exception as e:
                await send_error(guild, str(e))

        asyncio.create_task(delayed_send(message, target_channel, delay))


@copy_message_context.error
async def copy_message_context_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "Only server administrators can use this command.", ephemeral=True
        )


@tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    guild = interaction.guild

    error_text = f"{type(error).__name__}: {error}"

    # Try to notify the user
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                "An error occurred. The issue has been reported.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An error occurred. The issue has been reported.", ephemeral=True
            )
    except:
        pass

    # Send to error channel
    if guild:
        await send_error(guild, error_text)


@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")
    await tree.sync()
    print("Slash commands synced.")


client.run(TOKEN)
