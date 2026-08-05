    if message.content.startswith("#!module"):
        MODARCHIVE_RANDOM = "https://modarchive.org/index.php?request=view_random"
        async with message.channel.typing():
            async with aiohttp.ClientSession() as session:
                async with session.get(MODARCHIVE_RANDOM, allow_redirects=True) as r:
                    html = await r.text()
                    final_url = str(r.url)

                soup = BeautifulSoup(html, "html.parser")
                download_url = None

                h1 = soup.find("h1")
                if h1:
                    songtitle = h1.find(string=True, recursive=False)
                    songtitle = songtitle.strip()

                for a in soup.find_all("a", href=True):
                    if a.get_text() == "Download":
                        href = a["href"]

                        if href.startswith("http"):
                            download_url = href
                        else:
                            download_url = aiohttp.helpers.URL(final_url).join(aiohttp.helpers.URL(href))
                            download_url = str(download_url)
                        module_filename = download_url.rsplit("#", 1)[-1]
                        break

                for a in soup.find_all("a", href=True):
                    if a.get_text() == "Permalink":
                        module_page = f"https://modarchive.org/{a["href"]}"
                        break

                if download_url is None:
                    if "<h2>Sorry," in html:
                        await message.channel.send("modarchive is borked rn")
                    else:
                        await message.channel.send("sorry couldnt find download :(")
                    return

                # Layer3 integration
                if isinstance(message.channel, discord.VoiceChannel) and message.channel.name == "Layer3 Music":
                    await message.channel.send(f'["{songtitle}"]({module_page}), hit it layer3!!!!')
                    reader, writer = await asyncio.open_unix_connection("/tmp/layer3-x-rob.sock")
                    
                    writer.write(json.dumps({
                        "command": "url",
                        "guild_id": message.guild.id,
                        "channel_id": message.channel.id,
                        "url": download_url
                    }).encode() + b"\n")

                    await writer.drain()
                    await reader.readline()

                    writer.close()
                    await writer.wait_closed()
                    return

                async with session.get(download_url) as r:
                    module_data = await r.read()

            with tempfile.NamedTemporaryFile(dir="/tmp", delete=False) as infile:
                infile.write(module_data)
                input_path = infile.name

            output_path = input_path + ".ogg"

            try:
                proc = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-y",
                    "-i",
                    input_path,
                    "-q:a", "1",
                    "-threads", "0",
                    "-ar", "22050",
                    output_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )

                await proc.wait()

                if proc.returncode != 0:
                    await message.channel.send("conversion failed :(")
                    return

                with open(output_path, "rb") as f:
                    await message.channel.send(f'this one\'s called "{songtitle}" - [view in modarchive]({module_page})', file=discord.File(io.BytesIO(f.read()), filename=f"{module_filename}.ogg"))

            finally:
                for path in (input_path, output_path):
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass

        return
