def apply_dialect(text: str) -> str:
    for original, replacement in dialect_map.items():
        pattern = r'\b' + re.escape(original) + r'\b'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

SPLIT_BEFORE = {
    "oh", "but", "so", "also", "idk"
}
SPLIT_AFTER = {
    "too", "lol", "lmao"
}
def split_response(text):
    text = text.strip()
    if not text:
        return []

    protected = {}
    def protect(match):
        key = f"\x00{len(protected)}\x00"
        protected[key] = match.group(0)
        return key

    text = re.sub(r"```[\s\S]*?```", protect, text)
    text = re.sub(r"`[^`]+`", protect, text)
    text = re.sub(r"https?://\S+", protect, text)

    text = re.sub(r"[ \t]+", " ", text)
    processed = []

    paragraphs = text.splitlines()
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        paragraph = re.sub(r"([.!?])(?=\s|$)", r"\1\n", paragraph)

        # split commas only when there is enough text after them
        def comma_split(match):
            before = match.group(1).strip()
            after = match.group(2).strip()

            words_after = re.findall(r"\b[\w'-]+\b", after)
            if len(words_after) <= 3:
                return f"{before}, {after}"

            return f"{before}\n{after}"

        paragraph = re.sub(r"([^,\n]+),\s*([^,\n]+)", comma_split, paragraph)
        processed.append(paragraph)

    text = "\n".join(processed)
    lines = []
    current = []

    for token in re.split(r"(\s+)", text):
        if not token:
            continue

        if "\n" in token:
            if current:
                lines.append("".join(current).strip())
                current = []
            continue
        current.append(token)

        joined = "".join(current).strip()

        words = joined.split()
        if not words:
            continue

        last_word = re.sub(r"^[^\w'-]+|[^\w'-]+$", "", words[-1]).lower()
        if last_word in SPLIT_BEFORE and len(words) > 1:
            lines.append(joined)
            current = []
        elif last_word in SPLIT_AFTER and len(words) >= 3:
            lines.append(joined)
            current = []

    if current:
        lines.append("".join(current).strip())

    restored = []

    for line in lines:
        for key, value in protected.items():
            line = line.replace(key, value)

        if line.strip():
            restored.append(line.strip())

    restored = [item.replace(",", "") for item in restored]
    return restored

def guild_address(guild):
    slug = re.sub(r"[^a-z0-9]+", "-", guild.name.lower())
    slug = slug.strip("-")
    return f"{slug}-{str(guild.id)[-2:]}"

MNSSD_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat",
    "bottle", "bus", "car", "cat", "chair",
    "cow", "dining table", "dog", "horse", "motorbike",
    "person", "potted plant", "sheep", "sofa", "train",
    "screen"
]
def describe(image_url: str, conf_threshold: float = 0.35) -> str:
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            f.write(response.content)
            f.flush()
            image = cv2.imread(f.name)

            if image is None:
                return "Image isn't very clear"

            blob = cv2.dnn.blobFromImage(
                cv2.resize(image, (300, 300)),
                scalefactor=0.007843,
                size=(300, 300),
                mean=127.5
            )

            net.setInput(blob)
            detections = net.forward()

        labels = []

        for i in range(detections.shape[2]):
            conf = float(detections[0, 0, i, 2])
            if conf < conf_threshold:
                continue

            cls_id = int(detections[0, 0, i, 1])
            if 0 <= cls_id < len(MNSSD_CLASSES):
                labels.append(MNSSD_CLASSES[cls_id])

        if not labels:
            return "Image isn't very clear"

        counts = Counter(labels)
        objects = sorted(counts.items(), key=lambda x: x[1], reverse=True)

        if len(objects) == 1:
            name, count = objects[0]
            if count == 1:
                return f"An image containing a {name}"
            return f"An image containing {count} {name}s"

        top = [name for name, _ in objects[:5]]

        if len(top) == 2:
            return f"An image containing {top[0]} and {top[1]}"

        return ("An image containing " + ", ".join(top[:-1]) + f", and {top[-1]}")

    except Exception as e:
        print(e)
        return "An image you can't see"

def ocr(image_url: str) -> str | None:
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            f.write(response.content)
            f.flush()
            image = Image.open(f.name)

            text = pytesseract.image_to_string(image).strip()
            text = re.sub(r"\s+", " ", text)

            if text:
                return text

            return None

    except Exception as e:
        print(f"OCR error: {e}")
        return None

def describe_audio(path: str) -> str:
    try:
        y, sr = sf.read(path, dtype="float32", always_2d=False)
        if y.ndim > 1: y = np.mean(y, axis=1)
        y = y[:sr * 60]
        if sr != 16000: y = resample_poly(y, 16000, sr); sr = 16000

        length = len(y) / sr
        rms = np.array([np.sqrt(np.mean(y[i:i+2048]**2)) for i in range(0, len(y)-2048, 2048)])
        loudness = float(np.clip(np.mean(rms) * 3.75, 0, 1))

        freqs = np.fft.rfftfreq(len(y), 1/sr)
        active = freqs[np.abs(np.fft.rfft(y)) > np.abs(np.fft.rfft(y)).max() * 0.05]
        low_freq, high_freq = (int(active.min()), int(active.max())) if len(active) else (0, 0)

        pk, peaks = [], []
        for i in range(1, len(rms)-1):
            if rms[i] > rms[i-1] and rms[i] >= rms[i+1] and rms[i] > 0.2 and (not pk or i - pk[-1] >= 5):
                pk.append(i)
        peak_count = len(pk) * 2 - 2

        genre = (
            ("Sounds like someone talking" if loudness < 0.7 else "Sounds like someone yelling at the mic")
            if low_freq < 5 and high_freq > 3800 else
            ("Sounds like chill techno music" if loudness < 0.5 or low_freq > 16 else "Sounds like EDM music")
            if low_freq < 23 and high_freq > 1000 and peak_count > 3 else
            (("Sounds like upbeat drum music" if peak_count > length * 3 else "Sounds like rock music")
             if low_freq < 40 and loudness > 0.5 else "Sounds like acoustic music")
            if low_freq < 60 and high_freq > 2000 and peak_count > 3 else
            "Sounds like a sick rhythmic track" if loudness > 0.50 and peak_count > length and peak_count > 3 else
            ("Sounds like a funny loud sound" if loudness > 0.92 else "Sounds like a short sound effect")
            if length < 4 else
            "Sounds like ambient music or audio"
        )
        loud_label = (
            "Too quiet" if loudness < 0.01 else "Very quiet" if loudness < 0.05 else
            "Quiet" if loudness < 0.15 else "Pretty good" if loudness < 0.5 else
            "Loud" if loudness < 0.7 else "Very loud" if loudness < 0.92 else "EXTREMELY LOUD"
        )

        mins, secs = int(length // 60), int(length % 60)
        return f"{genre}, it's {loud_label}."
    except Exception as e:
        print(e)
        return "Couldn't read audio"

async def process_msg(message):
    parts = []
    content = message.clean_content.strip()

    if message.reference and message.reference.message_id:
        replied_to = message.reference.resolved

        if not isinstance(replied_to, discord.Message):
            try:
                replied_to = await message.channel.fetch_message(message.reference.message_id)
            except discord.NotFound:
                replied_to = None
            except discord.Forbidden:
                replied_to = None

        if replied_to:
            replied_content = replied_to.clean_content.strip()
            max_length = 64
            if len(replied_content) > max_length:
                replied_content = replied_content[:max_length - 3] + "..."
            parts.append(f'> {replied_content}\n\n')
        else:
            parts.append(f"> Replying to a past message from someone\n\n")

    if content:
        parts.append(content)

    for attachment in message.attachments:
        info = [f"name={attachment.filename}"]

        if attachment.content_type and attachment.content_type.startswith("image/"):
            desc, textcontent = await asyncio.gather(
                asyncio.to_thread(describe, attachment.url),
                asyncio.to_thread(ocr, attachment.url)
            )
            info.append(desc)

            if textcontent:
                info.append(f'Has text which reads: "{textcontent[:100]}"')

        elif attachment.content_type and attachment.content_type.startswith("audio/"):
            with tempfile.NamedTemporaryFile(suffix=os.path.splitext(attachment.filename)[1], delete=False) as f:
                response = requests.get(attachment.url, timeout=10)
                response.raise_for_status()
                f.write(response.content)
                tmp_path = f.name
            try:
                desc = await asyncio.to_thread(describe_audio, tmp_path)
                info.append(desc)
            finally:
                os.remove(tmp_path)

        parts.append(f"[Attachment: {', '.join(info)}]")

    for embed in message.embeds:
        embed_parts = []

        if embed.title:
            embed_parts.append(f"Title: {embed.title}")
        if embed.description:
            embed_parts.append(f"Description: {embed.description}")
        for field in embed.fields:
            embed_parts.append(
                f"{field.name}: {field.value}"
            )
        if embed.footer and embed.footer.text:
            embed_parts.append(
                f"Footer: {embed.footer.text}"
            )
        if embed.author and embed.author.name:
            embed_parts.append(
                f"Author: {embed.author.name}"
            )

        if embed_parts:
            parts.append("[Embed] " + " - ".join(embed_parts))


    final_msg = " ".join(parts)[:512]
    return f"{message.author.name} {f'(in #{message.channel})' if message.guild else ''}: {final_msg}"

async def websearch(query: str, status_callback=None):
    if status_callback:
        await status_callback("alr lemme look that up for ya")
    def search():
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=2))

    results = await asyncio.to_thread(search)

    if not results:
        return []

    url = results[0]["href"]
    if status_callback:
        await status_callback(f"found smth on {url} lemme read it...")

    try:
        async with aiohttp.ClientSession(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                )
            }
        ) as session:
            async with session.get(url, timeout=20) as response:
                response.raise_for_status()
                html = await response.text()
    except aiohttp.ClientResponseError as e:
        html = f"<p>HTTP error at webpage for '{query}': {e.status} {e.message}</p>"
    except aiohttp.ClientConnectorError as e:
        html = f"<p>Connection failed for webpage '{query}': {e}</p>"
    except aiohttp.TimeoutError:
        html = f"<p>Webpage for query '{query}' didn't respond in time.</p>"
    except aiohttp.ClientError as e:
        html = f"<p>Request error for webpage '{query}': {e}</p>"
    except Exception as e:
        html = f"<p>Unexpected browser error for query '{query}': {e}</p>"

    def parse():
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        root = soup.find("article") or soup

        paragraphs = [
            p.get_text(" ", strip=True)
            for p in root.find_all("p")
            if p.get_text(strip=True)
        ]

        text = "\n".join(paragraphs)
        text = re.sub(r"\s+", " ", text).strip()

        return text

    text = await asyncio.to_thread(parse)

    blocks = [
        block.strip()
        for block in re.split(r"\.\s+", text)
        if block.strip()
    ]

    packages = [{"url": str(url)}]
    seen = set()
    query_words = []

    for word in re.findall(r"\w+", query):
        key = word.lower()
        if key not in seen and len(key) > 2:
            seen.add(key)
            query_words.append(word)

    for keyword in query_words:
        keyword_lower = keyword.lower()

        match_index = None
        for i, block in enumerate(blocks):
            if keyword_lower in block.lower():
                match_index = i
                break

        packages.append({
            "keyword": keyword,
            "content": (
                ". ".join(blocks[match_index:match_index + 4])
                if match_index is not None
                else ""
            )
        })

    if status_callback:
        await status_callback(f"alr so um")

    return packages
