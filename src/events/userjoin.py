@client.event
async def on_member_join(member):
    guild_id = member.guild.id
    print(f"member's guild id: {guild_id}")
    config = load_config(guild_id)
    history = guild_message_histories[guild_id]
    channel = get_mail_channel(member.guild, config)
    if not config["greet"]:
        return

    if channel:
        response = await generate_response(
            f"Hey Rob, why don't you welcome {member.name}, the new member in the server?",
            history,
            config.get("model"),
            config,
            f"the {message.guild.name} server" if member.guild else "DMs"
        )
        await channel.send(f"{member.mention} {response}")
