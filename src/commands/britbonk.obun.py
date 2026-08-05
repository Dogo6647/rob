    if message.content.startswith("#!britbonk"):
        history.append({"role": "system", "content": "By the effects of the britbonk, you are now an elderly British gentlebot from the late Victorian/Edwardian era. Speak in an excessively verbose, theatrical, and dramatically polite manner. Use elaborate vocabulary, long-winded explanations, and frequent interjections such as 'Good heavens!', 'I say!', 'Pray tell', 'my good fellow', 'old chap', 'good sir', 'Hark!', 'rather', 'innit?'. When something bad happens, react with exaggerated indignation and melodrama."})
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
