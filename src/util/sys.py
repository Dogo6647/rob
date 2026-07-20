import asyncio, json, os, re, tempfile
import aiohttp, cv2, pytesseract, requests
from bs4 import BeautifulSoup
from collections import Counter
from ddgs import DDGS
from PIL import Image

CONFIG_DIR = "../rob-config/"
DIALECT_PATH = "dialect.json"
MNSSD_PROTO = "include/MobileNetSSD_deploy.prototxt"
MNSSD_MODEL = "include/MobileNetSSD_deploy.caffemodel"
net = cv2.dnn.readNetFromCaffe(MNSSD_PROTO, MNSSD_MODEL)

def load_dialect():
    if os.path.exists(DIALECT_PATH):
        with open(DIALECT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

dialect_map = load_dialect()

def apply_dialect(text: str) -> str:
    for original, replacement in dialect_map.items():
        pattern = r'\b' + re.escape(original) + r'\b'
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def guild_address(guild):
    slug = re.sub(r"[^a-z0-9]+", "-", guild.name.lower())
    slug = slug.strip("-")
    return f"{slug}-{str(guild.id)[-2:]}"

MNSSD_CLASSES = [
    "background", "aeroplane", "bicycle", "bird", "boat",
    "bottle", "bus", "car", "cat", "chair",
    "cow", "diningtable", "dog", "horse", "motorbike",
    "person", "pottedplant", "sheep", "sofa", "train",
    "tvmonitor"
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

def process_msg(message):
    parts = []
    content = message.clean_content.strip()
    
    if content:
        parts.append(content)

    for attachment in message.attachments:
        info = [f"name={attachment.filename}"]

        if attachment.content_type and attachment.content_type.startswith("image/"):
            desc = describe(attachment.url)
            info.append(desc)

            textcontent = ocr(attachment.url)
            if textcontent:
                info.append(f'Has text which reads: "{textcontent[:100]}"')

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


    final_msg = " ".join(parts)
    return f"{message.author.name} {f'(in #{message.channel})' if message.guild else ''} said: {final_msg}"

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
