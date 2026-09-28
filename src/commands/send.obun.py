    if message.content.startswith(f"{cmdprefix}send") and message.guild:
        parts = message.content.split(maxsplit=2)

        if len(parts) < 3:
            await message.channel.send(f"its like {cmdprefix}send <address> <message>")
            return

        target_address = parts[1]
        body = parts[2]

        sender_address = guild_address(message.guild)
        target_guild = None

        for guild in client.guilds:
            if guild_address(guild) == target_address:
                target_guild = guild
                break

        if target_guild is None:
            await message.channel.send("i couldn't find that server :(")
            return

        sender_cfg = load_config(message.guild.id)
        receiver_cfg = load_config(target_guild.id)

        if target_address not in sender_cfg["mailTrusted"]:
            await message.channel.send(f"that address isn't on your trusted list, run '{cmdprefix}trust {target_address}'")
            return

        if sender_address not in receiver_cfg["mailTrusted"]:
            await message.channel.send(f"that server hasn't trusted you yet, ask them to run '{cmdprefix}trust {sender_address}'")
            return

        channel = get_mail_channel(target_guild, receiver_cfg)

        if not channel:
            await message.channel.send("that server has nowhere i can deliver mail :(")
            return

        if not channel:
            await message.channel.send("delivery failed :(")
            return

        letter_text = (
            f"Dear {target_guild.name}:\n\n"
            f"{body}\n\n"
            f"- {message.author.name}"
        )

        embed = discord.Embed(
            title="📬 you've got mail!",
            description=f"a letter has arrived from **{message.guild.name}**.",
            color=0xF4D58D
        )

        await channel.send(
            embed=embed,
            view=LetterView(letter_text)
        )

        await message.channel.send("letter delivered! :D")
        return
