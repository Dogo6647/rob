CACHE_DIR = "/tmp/rob-cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def snapshot_message_history(guild_id):
    history = list(guild_message_histories[guild_id])
    with open(f"{CACHE_DIR}/{guild_id}.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)

def populate_guild_message_history(guild_id):
    print(f"\n:: Populating message history for guild {guild_id}...")
    try:
        with open(f"{CACHE_DIR}/{guild_id}.json", "r", encoding="utf-8") as f:
            history = json.load(f)
        guild_message_histories[guild_id] = deque(history, maxlen=12)
        print(f":: Done")
    except FileNotFoundError:
        snapshot_message_history(guild_id)
        print(f":: No previous entries; created a snapshot now.")

async def send_random_message():
    await client.wait_until_ready()
    while not client.is_closed():
        wait_time = random.randint(1, 10080) * 60
        print(f":: Waiting for {wait_time} seconds before sending a random message.")
        await asyncio.sleep(wait_time)
        for guild in client.guilds:
            config = load_config(guild.id)
            if config["randomlyMessage"]:
                channel = get_mail_channel(guild, config, force_general=True)
                if channel:
                    response = await generate_response(f"Say something as {client.user.name} based on the chat history; focus on the last sent message. If there are no messages, start the conversation by saying something interesting. Your entire response must be seven words or less.", guild_message_histories[guild.id], config.get("model"), config, f"the {guild.name} server")
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
