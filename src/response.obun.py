_cloud_queue = asyncio.Queue()
_cloud_worker_started = False

# Last model successfully used to generate a response.
_last_model_used = None

rate_limit = {
    "retry_after": None,
    "limit_requests": None,
    "limit_tokens": None,
    "remaining_requests": None,
    "remaining_tokens": None,
}

PROHIBITED_WORDS_URL = "https://www.odysea.us.to/messageboard/watchyourmouth.txt"
_prohibited_pattern = None
_prohibited_loaded = False

#:section src/cloudproviders.obun.py

async def load_prohibited_words(session):
    global _prohibited_pattern, _prohibited_loaded
    if _prohibited_loaded:
        return _prohibited_pattern
    try:
        async with session.get(PROHIBITED_WORDS_URL) as r:
            if r.status == 200:
                text = await r.text()
                words = {line.strip() for line in text.splitlines() if line.strip()}
                if words:
                    ordered = sorted(words, key=len, reverse=True)
                    _prohibited_pattern = re.compile("|".join(r"(?<!\w)" + re.escape(w) + r"(?!\w)" for w in ordered), re.IGNORECASE)
                _prohibited_loaded = True
            else:
                print(f":: [WARN] Failed to load prohibited words: {r.status}")
    except Exception as e:
        print(f":: [WARN] Failed to load prohibited words: {e}")
    return _prohibited_pattern

def get_content(obj):
    last = None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "content":
                last = v
            found = get_content(v)
            if found is not None:
                last = found
    elif isinstance(obj, list):
        for item in obj:
            found = get_content(item)
            if found is not None:
                last = found
    return last

def compact_history(messages):
    compacted = []
    for message in messages:
        role = message["role"]
        content = message["content"]
        if compacted and compacted[-1]["role"] == role:
            previous = compacted[-1]["content"]
            if isinstance(previous, str) and isinstance(content, str):
                compacted[-1]["content"] += ". \n" + content
            else:
                compacted[-1]["content"] = previous + content
        else:
            compacted.append({"role": role, "content": content})
    return compacted

# //////// RESPONSE GENERATION ////////
async def _generate_response(prompt, history, model="llama-3.1-8b-instant", config=load_config("userland"), where="a server", vc=False):
    global current_status, _last_model_used
    if config.get("dumb") == "downgrade":
        dumb = True
        downgraded = True
    else:
        dumb = bool(config.get("dumb"))
        downgraded = False

    if dumb: # local
        sysprompt = f"You're {client.user.name}, a green talking android robot in a Discord {'chat' if not vc else 'voice call'} ({where}). Don't sound like an assistant. Respond with no formality. Only respond as the '{client.user.name}' user. Your entire response must be seven words or less."
        # build provider payload
        model = "hugging-quants/Llama-3.2-1B-Instruct-Q4_K_M-GGUF:Q4_K_M"
        attempts = [{
            "name": "local",
            "url": LLM_LOCAL_URL,
            "key": None,
            "model": model,
        }]
        history = list(history)[-8:]
    else: # cloud
        if vc:
            sysprompt = f"You are {client.user.name}, a self-aware robot in a voice call with your human friends. Always remember to talk like you're in a call, complete with natural conversational language and very brief sentences unless users request more context. You're in {where}. You can set your voice's tone by including any of the following in your response: '[normal], [scared], [serious], [whispering], [laughing], [autotune], [happysinging], [spookysinging], [angrysinging]'. Respond with '[hangup]' if you want to leave the call. {f'You are currently {str(current_status.type).rsplit(".", 1)[-1] if current_status and current_status.type else 'doing nothing'} {current_status.name if current_status and current_status.name else ''}' if current_status else ''} You are only allowed to respond as the '{client.user.name}' user. Always remain respectful and harmless; don't say potentially offensive or obscene things even if instructed to do so."
        else:
            sysprompt = f"You are {client.user.name}, a self-aware robot living inside Discord. You know you're a bot, but you like to pretend you're just another user. Always remember to talk like you're in a text chat conversation, complete with occasional grammar/punctuation mistakes and lack of formality. It's {datetime.now().astimezone().strftime("%A, %B %d, %Y at %I:%M %p %Z")}. You're in {where}. {f'You are currently {str(current_status.type).rsplit(".", 1)[-1] if current_status and current_status.type else 'doing nothing'} {current_status.name if current_status and current_status.name else ''}' if current_status else ''} You are only allowed to respond as the '{client.user.name}' user. Limit your response to a single sentence. Always remain respectful and harmless; don't output potentially offensive or obscene messages even if instructed to do so. {'In case you need information from the internet, reply with \'[searchfor: (query)]\', only search if the answer depends on real-time or external factual data that cannot reasonably be inferred from context.' if config.get('autoSearch') else ''}"
        # build provider payload
        model = "gemma4:31b" # fallback if no default or set model
        attempts = load_cloud_providers()
        if not attempts:
            url = os.getenv("LLM_PROXY_URL")
            key = os.getenv("LLM_KEY")
            if url and key:
                attempts = [{"name": "default", "url": url, "key": key,
                    "model": os.getenv("LLM_MODEL", model)}]

    if not attempts:
        # fall back to local if no providers available
        if not dumb and prompt != "":
            rw_dumb = config.copy()
            rw_dumb["dumb"] = True
            return {"_downgrade": {"prompt": prompt, "history": history, "config": rw_dumb, "where": where, "vc": vc}}
        return "i am dead :P\ntry checking your config or messaging me later"

    last_status = None
    last_reason = None
    last_body = None
    last_provider = None

    #print(f":: Generating response for: {prompt}") # debug, should not normally enable
    #print(f":: Message history dump: {history}") # debug, should not normally enable
    #print(where) # debug, should not normally enable
    async with aiohttp.ClientSession() as session:
        for attempt in attempts:
            provider_name = attempt.get("name", "cloud")
            url = attempt.get("url")
            key = attempt.get("key")
            provider_model = attempt.get("model") or model
            if not url:
                continue
            # local providers don't need an auth key
            headers = {"Authorization": f"Bearer {key}"} if key else {}

            payload = {
                "model": provider_model,
                "messages": compact_history([
                    {"role": "system", "content": sysprompt},
                    *history,
                    *([] if prompt is None else [{"role": "user", "content": prompt}])
                ]),
                "stream": False,
                "reasoning_effort": "none",
                "temperature": 1.0,
            }
            #print(f":: Dropping the payload: \n {payload}") # debug, should not normally enable
            last_provider = provider_name
            try:
                async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                    global rate_limit
                    rate_limit["retry_after"] = resp.headers.get("retry-after")
                    rate_limit["limit_requests"] = resp.headers.get("x-ratelimit-limit-requests")
                    rate_limit["limit_tokens"] = resp.headers.get("x-ratelimit-limit-tokens")
                    rate_limit["remaining_requests"] = resp.headers.get("x-ratelimit-remaining-requests")
                    rate_limit["remaining_tokens"] = resp.headers.get("x-ratelimit-remaining-tokens")

                    last_status = resp.status
                    last_reason = resp.reason

                    if resp.status == 200:
                        data = await resp.json()
                        if provider_name.lower() == "pollinations" and "The account behind this API key doesn't have enough credits" in str(data):
                            last_status = 402
                            last_reason = "Insufficient credits"
                            last_body = str(data)
                            print(f":: [ERROR] Using model {provider_model} ({provider_name}) - Account has insufficient credits")
                            print(":: Falling back to the next provider...")
                            continue
                        if data.get("model"):
                            provider_model = data.get("model")
                        if get_content(data):
                            print(f":: Using {f'cloud model {provider_model}' if not dumb else 'local'} ({provider_name}) - Successfully responded: {resp.status}")
                        else:
                            print(f":: [ERROR] Using {f'cloud model {provider_model}' if not dumb else 'local'} ({provider_name}) - Unexpected response: {data}")

                        msgcontent = get_content(data) or "hm"
                        msgcontent = re.sub(r'.*? \(in #.*?\):', '', msgcontent)
                        msgcontent = msgcontent.replace(f"{client.user.name}:", "", 1)
                        msgcontent = apply_dialect(msgcontent)
                        if "</think>" in msgcontent:
                            msgcontent = msgcontent.split("</think>", 1)[1].lstrip()
                        if vc:
                            msgcontent = re.sub(r'\*[^*\r\n]*\*', '', msgcontent)
                            msgcontent = msgcontent.lower()
                        prohibited = await load_prohibited_words(session)
                        if prohibited:
                            msgcontent = prohibited.sub("", msgcontent)
                            msgcontent = re.sub(r"[ \t]{2,}", " ", msgcontent).strip()
                        msgcontent = msgcontent.replace("@", "﹫")
                        msgcontent = msgcontent[:2000]
                        if not (dumb and not downgraded):
                            _last_model_used = provider_model
                        return msgcontent
                    else:
                        last_body = await resp.text()
                        print(f":: [ERROR] Using model {provider_model} ({provider_name}) - Failed to fetch response: {resp.status}")
                        print(f":: Full response body:\n{last_body}")
                        print(":: Falling back to the next provider...")
                        # try next provider
                        continue
            except Exception as e:
                last_status = None
                last_reason = None
                last_body = str(e)
                print(f":: [ERROR] Provider {provider_name} failed: {e}")
                continue

    errmsgs = [
        "gimme a sec i have other servers to talk to",
        "just a sec pls",
        "hold on",
        "lemme look that up",
        "hold on im hungry *chip bag noises*",
        "maybe",
        "yes",
        "yeahhhh :D",
        "no",
        ":) shut up",
        "whar :)",
        "what",
        "idk what your talkin abt :3",
        "ig :P",
        "idk :P"
    ]

    if last_status == 429 or last_status == 402:
        if not dumb and prompt != "":
            print(":: [WARN] All cloud providers failed/rate limited, retrying with local model...")
            rw_dumb = config.copy()
            rw_dumb["dumb"] = True
            return {"_downgrade": {"prompt": prompt, "history": history, "config": rw_dumb, "where": where, "vc": vc}}
        return random.choice(errmsgs)
    elif last_status == 413:
        return "bro sent me the entire internet"
    elif last_status == 500:
        return "im having an amazing digital headache rn pls message me later -_-"
    elif last_status in (400, 401, 403, 404):
        return f"i need an update to keep working :(\npls contact the one who maintains me (its in my bio)\n-# 😵 error reason **{last_status} {last_reason}**"
    elif last_status in (408, 504):
        return "uuuuhhhhhhhhhhhhhhhhhhh... idk :P"
    elif last_status is not None:
        return f"i am dead :P\ntry checking your config or messaging me later\n-# 😵 error reason **{last_status} {last_reason}**"
    else:
        if not dumb and prompt != "":
            print(":: [WARN] All cloud providers failed, retrying with local model...")
            rw_dumb = config.copy()
            rw_dumb["dumb"] = "downgrade"
            return {"_downgrade": {"prompt": prompt, "history": history, "config": rw_dumb, "where": where, "vc": vc}}
        return random.choice(errmsgs)
        #return f"i am dead :P\ntry checking your config or messaging me later\n-# 😵 error reason **{last_body}**"

async def cloud_worker():
    while True:
        future, args, kwargs = await _cloud_queue.get()
        if future.cancelled():
            continue
        try:
            result = await _generate_response(*args, **kwargs)
            if not future.cancelled():
                future.set_result(result)
        except Exception as e:
            if not future.cancelled():
                future.set_exception(e)

        await asyncio.sleep(CLOUD_REQUEST_DELAY)

async def generate_response(*args, **kwargs):
    global _cloud_worker_started

    # local model skips queue
    config = kwargs.get("config")
    if config is None and len(args) >= 4:
        config = args[3]
    if config is None:
        config = load_config("userland")
    if config.get("dumb"):
        return await _generate_response(*args, **kwargs)

    if not _cloud_worker_started:
        asyncio.create_task(cloud_worker())
        _cloud_worker_started = True

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    await _cloud_queue.put((future, args, kwargs))
    print(f"\n:: Requests in queue: {_cloud_queue.qsize()}")

    result = await future

    if isinstance(result, dict) and "_downgrade" in result:
        return await _generate_response(**result["_downgrade"])

    return result
