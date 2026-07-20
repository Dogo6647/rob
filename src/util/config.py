import discord, json, os
from discord.ext import commands

OWNER_ID = os.getenv("OWNER_ID", None)
CONFIG_DIR = "../rob-config/"

def load_config(guild_id):
    config_path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return json.load(f)
    return {"randomlyMessage": False, "responseFrequency": 4, "listen": True, "dumb": False, "mailTrusted": [], "mailChannel": None}

def save_config(guild_id, config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config_path = os.path.join(CONFIG_DIR, f"{guild_id}.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)

def get_mail_channel(guild, config):
    # explicitly configured channel prioritized++
    if config.get("mailChannel"):
        channel = guild.get_channel(config["mailChannel"])
        if channel and isinstance(channel, discord.TextChannel) and channel.permissions_for(guild.me).send_messages:
            return channel

    # try common names
    preferred = ["general", "main", "chat", "lobby", "discussion"]
    for name in preferred:
        for channel in guild.text_channels:
            if channel.name.lower() == name:
                if channel.permissions_for(guild.me).send_messages:
                    return channel

    # channels containing "general"
    for channel in guild.text_channels:
        if "general" in channel.name.lower():
            if channel.permissions_for(guild.me).send_messages:
                return channel

    # first writable text channel as last resort
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            return channel

    return None

async def has_rob_admin(ctx: commands.Context):
    if not ctx.guild:
        return False

    role = discord.utils.get(ctx.guild.roles, name="RobAdmin")
    if role not in ctx.author.roles and not ctx.author.guild_permissions.administrator and str(ctx.author.id) != str(OWNER_ID):
        await ctx.send("...you dont have the RobAdmin role yk\ngonna need that to change my settings :3", ephemeral=True)
        return False
        
    return True