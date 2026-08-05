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
