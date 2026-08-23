    if message.content.startswith("#!custombonk"):
        bonk = message.content.split("#!custombonk", 1)[1].strip()
        history.append({"role": "system", "content": f"{bonk}"})
        async with message.channel.typing():
            response = await generate_response(
                "BANNNNNNGGGG!!!!! Complain about being bonked in the head.",
                history,
                config.get("model"),
                config,
                f"the {message.guild.name} server" if message.guild else "DMs"
            )
        await message.channel.send(f"🪄💥 {response}")
        return
