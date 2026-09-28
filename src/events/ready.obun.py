history_semaphore = asyncio.Semaphore(3)
async def fetch_channel_messages(channel):
    async with history_semaphore:
        try:
            return [
                message async for message in channel.history(
                    limit=guild_message_histories[0].maxlen
                )
            ]
        except Exception:
            return []
        
async def populate_guild_message_history(guild):
    print(f"\n:: Populating message history for guild {guild.id}...")
    results = await asyncio.gather(
        *(fetch_channel_messages(channel)
          for channel in guild.text_channels)
    )

    messages = [message for channel_messages in results for message in channel_messages]
    messages.sort(key=lambda m: m.created_at)
    messages = messages[-guild_message_histories[0].maxlen:]

    guild_message_histories[guild.id].clear()

    processed = await asyncio.gather(
        *(process_msg(message) for message in messages)
    )

    for message, content in zip(messages, processed):
        guild_message_histories[guild.id].append({
            "role": "assistant" if message.author == client.user else "user",
            "content": content,
        })
    print(f":: Done")

async def send_random_message():
    await client.wait_until_ready()
    while not client.is_closed():
        wait_time = random.randint(1, 4320) * 60
        print(f":: Waiting for {wait_time} seconds before sending a random message.")
        await asyncio.sleep(wait_time)
        for guild in client.guilds:
            config = load_config(guild.id)
            if config["randomlyMessage"]:
                channel = get_mail_channel(guild, config, force_general=True)
                if channel:
                    response = await generate_response("Say something as Rob based on the chat history; focus on the last sent message. If there are no messages, start the conversation by saying something interesting.", guild_message_histories[guild.id], config.get("model"), config, f"the {guild.name} server")
                    await channel.send(response)

@client.event
async def on_ready():
    global changelog_checked

    print(f':: Logged in as {client.user}')
    #print(":: Guilds:") # should not normally be enabled in large instances
    #for guild in client.guilds:
    #    print(f"- {guild.name} | owned by {guild.owner} | {guild.member_count} members")

    if not changelog_checked:
        changelog_checked = True
        await broadcast()

    client.loop.create_task(send_random_message())
    change_status.start()
