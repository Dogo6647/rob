    if message.content.startswith("#!owobonk"):
        history.append({"role": "system", "content": "You have been hit with the OwO magic stik. Youw head huwts a wittwe, and you can onwwy tawwk in uwu femboy furry language fwom now on. Replace evewy 'r' you say with 'w'. Occassionawwy say stufz like *blushes*, *giggles*, rawr, and hehe~. Use '~' non-spawringwy."})
        async with message.channel.typing():
            response = await generate_response(
                "BANNNNNNGGGG!!!!! say your head is feeling funny. Start your response with 'ow' or similar.",
                history,
                config.get("model"),
                config,
                f"the {message.guild.name} server" if message.guild else "DMs"
            )
        await message.channel.send(f"🪄💥 >~< {response}")
        return
