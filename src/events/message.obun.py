@client.event
async def on_message(message):
    if message.author == client.user:
        return # Ignore itself lol
    
    if message.guild:
        guild_id = message.guild.id
        config = load_config(guild_id)
        guild_message_histories[guild_id].append({"role": "user", "content": process_msg(message)})
        history = guild_message_histories[guild_id]
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return
    else:
        user_id = message.author.id
        userconfig = "userland"
        config = load_config(userconfig)
        dm_message_histories[user_id].append({"role": "user", "content": process_msg(message)})
        history = dm_message_histories[user_id]
    
    # --- BOT COMMANDS ---
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
    # ------------------
    
    if not config["listen"]:
        return
    
    should_respond = message.mention_everyone or client.user.mentioned_in(message) or random.random() < (config["responseFrequency"] / 100)
    should_reply = client.user.mentioned_in(message) or message.reference is not None
    
    if should_respond:
        async with message.channel.typing():
            num_responses = random.choices([1, 2, 3], weights=[75, 20, 5], k=1)[0]

            for i in range(num_responses):
                if random.random() < tin_can_chance:
                    if random.randint(0, 1) == 0:
                        response = "*tin can noises*"
                    else:
                        response = "https://odysea.us.to/assets/dump/iamarobot.mov"
                else:
                    response = await generate_response(
                        'respond' if i == 0 else 'continue Rob\'s previous message',
                        history,
                        config.get("model"),
                        config.get("dumb"),
                        f"the {message.guild.name} server" if message.guild else "DMs"
                    )

                if (history and history[-1]["role"] == "assistant" and history[-1]["content"] == response):
                    continue

                history.append({"role": "assistant", "content": response})
                if should_reply and i == 0:
                    await message.reply(response,  mention_author=False)
                else:
                    await message.channel.send(response)

                # sleep between responses, not after the last one
                if i < num_responses - 1:
                    await asyncio.sleep(random.uniform(0.5, 2))

        if message.guild:
            guild_daily_stats[message.guild.id] += num_responses
