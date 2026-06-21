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
                info.append(f'Has text which reads: "{textcontent[:500]}"')

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
