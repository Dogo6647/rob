def is_private_channel(channel, guild):
    return not channel.permissions_for(guild.default_role).view_channel



def get_mail_channel(guild, config, force_general=False):
    # explicitly configured channel prioritized++
    if config.get("mailChannel") and not force_general:
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


def get_moderation_channel(guild, config):
    # explicitly configured channel prioritized++
    if config.get("staffChannel"):
        channel = guild.get_channel(config["staffChannel"])
        if (
            isinstance(channel, discord.TextChannel)
            and channel.permissions_for(guild.me).send_messages
            and is_private_channel(channel, guild)
        ):
            return channel

    # only search private channels
    candidates = []
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages and is_private_channel(channel, guild):
            candidates.append(channel)

    # try common names
    preferred = [
        "mod-logs",
        "modlog",
        "server-logs",
        "logs",
        "automod",
        "moderator-only",
        "mod-chat",
        "moderator-chat",
        "staff-general",
        "staff-chat",
    ]

    for name in preferred:
        for channel in candidates:
            if channel.name.lower() == name:
                return channel

    # channels containing "staff" or "mod"
    for channel in candidates:
        if "staff" in channel.name.lower() or "mod" in channel.name.lower():
            return channel

    # first writable private text channel as last resort
    return candidates[0] if candidates else None
