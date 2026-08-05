async def send_random_message():
    await client.wait_until_ready()
    while not client.is_closed():
        wait_time = random.randint(1, 480) * 60
        print(f":: Waiting for {wait_time} seconds before sending a random message.")
        await asyncio.sleep(wait_time)
        for guild in client.guilds:
            config = load_config(guild.id)
            general_channels = [channel for channel in guild.text_channels if "general" in channel.name.lower()]
            if config["randomlyMessage"] and general_channels:
                channel = random.choice(general_channels)
                if channel:
                    response = await generate_response("Say something as Rob based on the chat history; focus on the last sent message. If there are no messages, start the conversation by saying something interesting.", guild_message_histories[guild.id], config.get("model"), config, f"the {guild.name} server")
                    await channel.send(response)
                    guild_message_histories[guild.id].append({"role": "assistant", "content": response}) # {client.user.name} (you)

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
