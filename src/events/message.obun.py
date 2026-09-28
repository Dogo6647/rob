@client.event
async def on_message(message):
    if message.guild:
        guild_id = message.guild.id
        config = load_config(guild_id)
        if config["listen"] and message.author != client.user:
            guild_message_histories[guild_id].append({"role": "user", "content": await process_msg(message)})
        if len(guild_message_histories[guild_id]) < 2:
            await populate_guild_message_history(message.guild)
        history = guild_message_histories[guild_id]
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return
    else:
        user_id = message.author.id
        userconfig = "userland"
        config = load_config(userconfig)
        if config["listen"] and message.author != client.user:
            dm_message_histories[user_id].append({"role": "user", "content": await process_msg(message)})
        history = dm_message_histories[user_id]

    if message.author == client.user:
        history.append({"role": "assistant", "content": await process_msg(message)})
        if message.guild:
            guild_daily_stats[message.guild.id] += 1
        return # Ignore itself lol
    
    # --- BOT COMMANDS ---
    cmdprefix =  os.getenv("CMD_PREFIX", "#!")
    #:section src/commands/option.obun.py
    #:section src/commands/help.obun.py
    #:section src/commands/about.obun.py
    #:section src/commands/eval.obun.py
    #:section src/commands/address.obun.py
    #:section src/commands/trustuntrust.obun.py
    #:section src/commands/send.obun.py
    #:section src/commands/phonebook.obun.py
    #:section src/commands/dadjoke.obun.py
    #:section src/commands/owobonk.obun.py
    #:section src/commands/britbonk.obun.py
    #:section src/commands/custombonk.obun.py
    #:section src/commands/search.obun.py
    #:section src/commands/quota.obun.py
    #:section src/commands/module.obun.py
    # ------------------
    
    if not config["listen"]:
        return
    
    should_respond = message.mention_everyone or client.user.mentioned_in(message) or random.random() < (max(0, min(config["responseFrequency"], 100)) / 100)
    should_reply = False
    if client.user.mentioned_in(message):
        should_reply = True
    elif message.reference is not None:
        replied_to = await message.channel.fetch_message(message.reference.message_id)
        should_reply = replied_to.author.id == client.user.id
    should_react = config["responseFrequency"] > 0 and random.random() < (max(0, min(2, 100)) / 100)
    
    if should_react:
        if not should_reply:
            await asyncio.sleep(2)
        reaction_bullets = "\n".join(
            f"- {reaction.emoji}"
            for reaction in message.reactions
        )
        response = await generate_response(
            f"""
React to the latest message using a single emoji. Only output the emoji. 

Examples of common reactions you can use: 
- 🔥 for something cool,
- 😭 for something wild,
- 😛 for something that's fun in a chaotic way,
- 🥹 for something wholesome or something you've been hyped for,
- 😧 for something worrying or concerning,
- 🤒 for something unfortunate,
- 😱 for something that's sarcastically a shocker,
- 😂 in ironic response to otherwise groan-worthy jokes,
- 🎉 for unexpected humor,
- 👀 for something interesting or teasing,
- ✅ or ⬆️ to show agreement,
- ❌ to show disagreement.

{f"Or preferably, use one of these already attached reactions:\n{reaction_bullets}" if reaction_bullets else ""}
""",
            history,
            config.get("model"),
            config,
            f"the {message.guild.name} server" if message.guild else "DMs"
        )

        def first_emoji(text):
            for char in text:
                cp = ord(char)
                if (
                    0x1F300 <= cp <= 0x1FAFF
                    or 0x2600 <= cp <= 0x26FF
                    or 0x2700 <= cp <= 0x27BF
                    or 0x1F1E6 <= cp <= 0x1F1FF
                ):
                    return char
            return None

        if first_emoji(response):
            print(":::: (Reacted to a message)")
            await message.add_reaction(first_emoji(response))
        else:
            print(":::: [ERROR] Could not react; bot must've sent a non-emoji character.")

    if should_respond and (
    (("join" in message.content
    or "hop on" in message.content) and
    ("vc" in message.content or 
    "voice" in message.content)) or
    "mic up" in message.content):
        if await join_user_voice(message.author, message.guild):
            pass
        else:
            await message.channel.send("...but youre not in a voice chat")
        return

    if should_respond:
        # Cooldown
        now = time.monotonic()
        last = user_cooldowns.get(message.author.id, 0)
        if now - last < COOLDOWN:
            print(f":: [WARN] Cooldown triggered by {re.sub(r"[a-zA-Z]", "x", message.author.name)} ({message.author.id})")
            return
        user_cooldowns[message.author.id] = now

        async with message.channel.typing():
            if random.random() < tin_can_chance:
                if random.randint(0, 1) == 0:
                    response = "*tin can noises*"
                else:
                    if datetime.now().month == 10:
                        response = "https://odysea.us.to/assets/dump/spookyscaryskeletons.mp4"
                    else:
                        response = "https://odysea.us.to/assets/dump/iamarobot.mov"
            else:
                response = await generate_response(
                    "Respond as Rob to the last message.",
                    history,
                    config.get("model"),
                    config,
                    f"the {message.guild.name} server" if message.guild else "DMs"
                )

            if not message.guild:
                history.append({"role": "assistant", "content": f"Rob: {response}"})

            if "[searchfor:" in response:
                should_reply = False

                async def update_status(text):
                    await message.channel.send(text)

                q = response[len("[searchfor:"): -1].strip()
                result = await websearch(q, update_status)

                response = await generate_response(
                    f"Summarize the following text so that it's relevant to the conversation: '{result}'. Use the amount of words necessary to make a detailed explanation. DO NOT use [searchfor: (query)] again.",
                    history,
                    config.get("model"),
                    config,
                    f"the {message.guild.name} server" if message.guild else "DMs"
                )

            messages = split_response(response)
            for i, chunk in enumerate(messages):
                if should_reply and i == 0 and not "[searchfor:" in response:
                    await message.reply(chunk, mention_author=True if message.author.id in frens else False)
                else:
                    await message.channel.send(chunk)

                # sleep between responses
                if i < len(messages) - 1:
                    await asyncio.sleep(random.uniform(0.5, 3))
