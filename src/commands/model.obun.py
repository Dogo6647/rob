    if message.content.startswith(f"{cmdprefix}model"):
        if config.get("dumb"):
            await message.channel.send(f"this server has dumb mode enabled, so im running on the local model :P")
            return

        try:
            last_model = _last_model_used
        except NameError:
            last_model = None

        if last_model:
            await message.channel.send(f"last model i used was `{last_model}`")
        else:
            await message.channel.send("sorry haven't generated any response yet")
        return
