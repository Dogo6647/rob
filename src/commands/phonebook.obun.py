    if message.content.startswith(f"{cmdprefix}phonebook") and message.guild:
        trusted = config.get("mailTrusted", [])

        if not trusted:
            await message.channel.send(
                f"this server's phonebook is empty :(\nuse `{cmdprefix}trust <address>` to add servers"
            )
            return

        entries = []

        for address in trusted:
            guild_name = "unknown server"

            for guild in client.guilds:
                if guild_address(guild) == address:
                    guild_name = guild.name
                    break

            entries.append((guild_name, address))

        view = PhonebookView(entries, message.author.id)
        await message.channel.send(embed=view.make_embed(), view=view)
        return
