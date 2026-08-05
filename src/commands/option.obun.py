    if message.content.startswith("#!option") and message.guild:
        parts = message.content.split()
        if len(parts) == 2:
            await message.channel.send(f"its `{config[parts[1]]}`")
            return
        if len(parts) < 3:
            await message.channel.send("#!option <optionId> <value>\nthats how you do it btw ;3")
            await message.channel.send(
                "heres my options you can change :)\n" +
                "\n".join(f"- `{key}` - set to **{value}**" for key, value in config.items())
            )
            return
        
        role = discord.utils.get(message.guild.roles, name="RobAdmin")
        if role not in message.author.roles and not message.author.guild_permissions.administrator and str(message.author.id) != str(OWNER_ID):
            await message.channel.send("...you dont have the RobAdmin role yk\ngonna need that to change my settings :3")
            return
        
        option, value = parts[1], parts[2]
        if option in config:
            if not option == "model" and not option == "mailChannel" and not option == "mailTrusted":
                TRUE_VALUES = {"enable", "enabled", "on", "true", "yes"}
                FALSE_VALUES = {"disable", "disabled", "off", "false", "no"}
                if value.lower() in TRUE_VALUES:
                    config[option] = True
                elif value.lower() in FALSE_VALUES:
                    config[option] = False
                else:
                    try:
                        config[option] = int(value)
                    except ValueError:
                        await message.channel.send("no not like that :X\nuse `enable`, `disable`, or a number")
                        return
            elif option == "mailChannel":
                match = re.match(r"<#(\d+)>", value)

                if match:
                    config[option] = int(match.group(1))
                elif value.isdigit():
                    config[option] = int(value)
                else:
                    await message.channel.send("give me a channel mention or channel id")
                    return
            elif option == "mailTrusted" or option == "model":
                await message.channel.send("you cannot change that part of my config with #!option :X")
                return
            else:
                config[option] = value
            save_config(guild_id, config)
            await message.channel.send(f"alr, `{option}` is now `{value}` :)")
        else:
            await message.channel.send(f"umm idk what a `{option}` is :/")
        return

