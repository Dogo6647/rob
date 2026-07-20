import os, random
from asyncio import sleep
from datetime import datetime
from discord import Intents, Message
from discord.ext import commands, tasks
from discord.gateway import DiscordWebSocket
from collections import defaultdict, deque

from .ws import MobileWebSocket
from util.config import load_config, save_config, get_mail_channel
from util.gen import generate_response
from util.sys import process_msg, websearch
from util.status import STATUSES

CHANGELOG_FILE = "changelog.txt"
ENABLED_COGS = ["config", "dev", "info", "mail", "misc", "util"]
TIN_CAN_CHANCE = 0.005

class Rob(commands.Bot):
    changelog_checked = False
    # Store message history per server and per user in DMs
    dm_message_histories = defaultdict(lambda: deque(maxlen=24))
    guild_message_histories = defaultdict(lambda: deque(maxlen=24))
    guild_daily_stats = defaultdict(int)
    stats_day = datetime.utcnow().date()

    def __init__(self):
        intents = Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.members = True
        intents.dm_messages = True
        intents.message_content = True

        super().__init__(
            command_prefix="#!",
            intents=intents,
            help_command=None # this is overwritten in the Info cog
        )

    async def setup_hook(self):
        for cog in ENABLED_COGS:
            try:
                await self.load_extension(f"cogs.{cog}")
                print(f":: Cog {cog} loaded successfully")
            except Exception as e:
                print(f":: Cog {cog} failed to load: {e}")
        await self.tree.sync()

    async def on_ready(self):
        print(f':: Logged in as {self.user}')
        #print(":: Guilds:") # should not normally be enabled in large instances
        #for guild in client.guilds:
        #    print(f"- {guild.name} | owned by {guild.owner} | {guild.member_count} members")

        if not changelog_checked:
            changelog_checked = True
            await self.broadcast()

        self.loop.create_task(self.send_random_message)
        self.change_status.start()

    async def on_guild_join(guild):
        config = load_config(guild.id)
        save_config(guild.id, config)
        channel = get_mail_channel(guild, config)
        if channel:
            await channel.send("hi! visit https://dogo6647.github.io/rob to learn how to set me up :)")

    async def on_message(self, message: Message):    
        if message.guild:
            guild_id = message.guild.id
            config = load_config(guild_id)
            if config["listen"] and message.author != self.user:
                self.guild_message_histories[guild_id].append({
                    "role": "user",
                    "content": process_msg(message)
                })
            history = self.guild_message_histories[guild_id]
            if not message.channel.permissions_for(message.guild.me).send_messages:
                return
        else:
            user_id = message.author.id
            userconfig = "userland"
            config = load_config(userconfig)
            if config["listen"] and message.author != self.user:
                self.dm_message_histories[user_id].append({
                    "role": "user",
                    "content": process_msg(message)
                })
            history = self.dm_message_histories[user_id]

        if message.author == self.user:
            history.append({"role": "assistant", "content": message.content})
            return # Ignore itself lol
        
        if not config["listen"]:
            return
        
        should_respond = message.mention_everyone or self.user.mentioned_in(message) or random.random() < (config["responseFrequency"] / 100)
        should_reply = self.user.mentioned_in(message) or message.reference is not None
        
        if should_respond:
            async with message.channel.typing():
                num_responses = random.choices([1, 2], weights=[85, 15], k=1)[0]

                for i in range(num_responses):
                    if random.random() < TIN_CAN_CHANCE:
                        if random.randint(0, 1) == 0:
                            response = "*tin can noises*"
                        else:
                            response = "https://odysea.us.to/assets/dump/iamarobot.mov"
                    else:
                        #print('response' if i == 0 else 'continuation')
                        response = await generate_response(
                            'respond' if i == 0 else 'continue Rob\'s previous message',
                            history,
                            config.get("model"),
                            config.get("dumb"),
                            f"the {message.guild.name} server" if message.guild else "DMs"
                        )

                    if (history and history[-1]["role"] == "assistant" and history[-1]["content"] == response):
                        continue

                    if "[searchfor: " in response:
                        should_reply = False

                    if should_reply and i == 0:
                        await message.reply(response,  mention_author=False)
                    else:
                        if "[searchfor: " in response:
                            async def update_status(text):
                                await message.channel.send(text)

                            q = response[len("[searchfor:"): -1].strip()
                            result = await websearch(q, update_status)
                            response = await generate_response(
                                f"Summarize the following text so that it's relevant to the conversation: '{result}'. Use the amount of words necessary to make a detailed explanation.",
                                history,
                                config.get("model"),
                                config.get("dumb"),
                                f"the {message.guild.name} server" if message.guild else "DMs"
                            )
                            await message.channel.send(response)
                        else:
                            await message.channel.send(response)

                    # sleep between responses, not after the last one
                    if i < num_responses - 1:
                        await sleep(random.uniform(0.5, 2))

            if message.guild:
                self.guild_daily_stats[message.guild.id] += num_responses
                
    async def change_status(self):
        global current_status
        current_status = random.choice(STATUSES)
        if current_status is None:
            await self.change_presence(activity=None)
        else:
            await self.change_presence(activity=current_status)
        print(f"Changed status to: {current_status.name if current_status else 'nothing'}")

    async def reset_stats(self):
        today = datetime.utcnow().date()
        if today != self.stats_day:
            self.guild_daily_stats.clear()
            self.stats_day = today

    async def broadcast(self):
        if not os.path.exists(CHANGELOG_FILE):
            return

        with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
            raw = f.read()

        if raw.lstrip().startswith("[sent]"):
            return

        changelog_text = raw.split("[sent]", 1)[0].strip()
        if not changelog_text:
            return

        print(":: Broadcasting changelog...")

        for guild in self.guilds:
            try:
                config = load_config(guild.id)
                channel = get_mail_channel(guild, config)

                if not channel:
                    continue

                owner_ping = guild.owner.mention if guild.owner else ""

                await channel.send(
                    f"{owner_ping if '[noping]' not in changelog_text else ""}\n"
                    f"{changelog_text.replace('[noping]', '')}"
                )

            except Exception as e:
                print(f":: Failed to send changelog to {guild.name}: {e}")

        with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
            f.write("[sent]\n" + raw)

        print(":: Changelog marked as sent.")

    async def send_random_message(self):
        await self.wait_until_ready()
        while not self.is_closed():
            wait_time = random.randint(1, 480) * 60
            print(f":: Waiting for {wait_time} seconds before sending a random message.")
            await sleep(wait_time)
            for guild in self.guilds:
                config = load_config(guild.id)
                general_channels = [channel for channel in guild.text_channels if "general" in channel.name.lower()]
                if config["randomlyMessage"] and general_channels:
                    channel = random.choice(general_channels)
                    if channel:
                        response = await generate_response(
                            "Say something as Rob based on the chat history; focus on the last sent message. If there are no messages, start the conversation by saying something interesting.",
                            self.guild_message_histories[guild.id],
                            config.get("model"),
                            config.get("dumb"),
                            f"the {guild.name} server"
                        )
                        await channel.send(response)
                        self.guild_message_histories[guild.id].append({"role": "assistant", "content": response}) # {client.user.name} (you)

DiscordWebSocket.identify = MobileWebSocket.identify
