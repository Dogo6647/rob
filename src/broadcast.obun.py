async def broadcast():
    if not os.path.exists(CHANGELOG_FILE):
        return

    with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
        raw = f.read()

    if raw.lstrip().startswith("[sent]"):
        return

    changelog_text = raw.split("[sent]", 1)[0].strip()
    if not changelog_text:
        return

    print(":: Broadcasting changelog...")

    for guild in client.guilds:
        try:
            config = load_config(guild.id)
            channel = get_mail_channel(guild, config)

            if not channel or not config.get("mailChannel") or not config.get("announcements"):
                continue

            owner_ping = guild.owner.mention if guild.owner else ""

            await channel.send(
                f"{owner_ping if '[noping]' not in changelog_text else ""}\n"
                f"{changelog_text.replace('[noping]', '')}\n"
                "-# ⚠️ Most Rob updates are sent through the official server, but the bot itself is used to send important announcements like this one from time to time such as major updates and service statuses. If you would like to disable this behavior, use `#!option announcements disable`."
            )
            print(f":: Sent to {guild.id} successfully")

        except Exception as e:
            print(f":: Failed to send changelog to {guild.name} ({guild.id}): {e}")

    with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
        f.write("[sent]\n" + raw)

    print(":: Changelog marked as sent.")
