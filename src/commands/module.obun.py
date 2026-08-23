    if message.content.startswith("#!module"):
            MODARCHIVE_RANDOM = "https://modarchive.org/index.php?request=view_random"
            MOD_EXTENSIONS = {".mod", ".xm", ".it", ".s3m", ".669", ".amf", ".ams", ".dbm", ".dmf",
                              ".dsm", ".far", ".mdl", ".med", ".mtm", ".okt", ".ptm", ".stm", ".ult",
                              ".umx", ".mt2", ".psm", ".mo3", ".oxm", ".mptm", ".ppm", ".mmcmp"}
            async with message.channel.typing():
                async with aiohttp.ClientSession(
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0 Safari/537.36"
                        )
                    }
                ) as session:
                    parts = message.content.split(None, 2)
                    command = parts[1].lower() if len(parts) > 1 else "random"

                    module_page_url = None

                    if command in ("random", ) or message.content.strip() == "#!module":
                        async with session.get(MODARCHIVE_RANDOM, allow_redirects=True) as r:
                            html = await r.text()
                            final_url = str(r.url)
                        module_page_url = final_url

                    elif command == "search":
                        if len(parts) < 3:
                            await message.channel.send("its like #!module search <query>")
                            return
                        query = parts[2].strip()
                        search_url = f"https://modarchive.org/index.php?request=search&query={aiohttp.helpers.URL(query).path}&submit=Find&search_type=filename_or_songtitle"
                        async with session.get(search_url, allow_redirects=True) as r:
                            html = await r.text()
                        soup = BeautifulSoup(html, "html.parser")
                        for a in soup.find_all("a", href=True):
                            if any(a.get_text().lower().endswith(ext) for ext in MOD_EXTENSIONS):
                                href = a["href"]
                                module_page_url = f"https://modarchive.org/{href}" if not href.startswith("http") else href
                                break
                        if module_page_url is None:
                            await message.channel.send("couldnt find anything :(")
                            return

                    elif command in ("spotlit", "featured"):
                        page = random.randint(1, 158)
                        featured_url = f"https://modarchive.org/index.php?format=&search_type=&query=featured&request=view_chart&page={page}&submit=Jump%21"
                        async with session.get(featured_url, allow_redirects=True) as r:
                            html = await r.text()
                        soup = BeautifulSoup(html, "html.parser")
                        candidates = [
                            a["href"] for a in soup.find_all("a", href=True, class_="chart-listing-title")
                        ]
                        if not candidates:
                            if "<h2>Sorry," in html:
                                await message.channel.send("modarchive is borked rn")
                            else:
                                await message.channel.send("modarchive returned something unexpected")
                            return
                        href = random.choice(candidates)
                        module_page_url = f"https://modarchive.org/{href}" if not href.startswith("http") else href

                    elif command == "artist":
                        if len(parts) < 3:
                            await message.channel.send("its like #!module artist <artist>")
                            return
                        artist = parts[2].strip()
                        artist_url = f"https://modarchive.org/index.php?query={aiohttp.helpers.URL(artist).path}&submit=Find&request=search&search_type=guessed_artist"
                        async with session.get(artist_url, allow_redirects=True) as r:
                            html = await r.text()
                        soup = BeautifulSoup(html, "html.parser")
                        candidates = [
                            a["href"] for a in soup.find_all("a", href=True)
                            if any(a.get_text().lower().endswith(ext) for ext in MOD_EXTENSIONS)
                        ]
                        if not candidates:
                            if "<h2>Sorry," in html:
                                await message.channel.send("modarchive is borked rn")
                            else:
                                await message.channel.send("couldnt find anything :(")
                            return
                        href = random.choice(candidates)
                        module_page_url = f"https://modarchive.org/{href}" if not href.startswith("http") else href

                    else:
                        await message.channel.send("its like #!module <random|search|spotlit|featured|artist>")
                        return

                    if command != "random" and message.content.strip() != "#!module":
                        async with session.get(module_page_url, allow_redirects=True) as r:
                            try:
                                html = await r.text()
                            except:
                                await message.channel.send("cant reach modarchive rn")
                                return
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
                        "-ar", "32000",
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
