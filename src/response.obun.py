_cloud_queue = asyncio.Queue()
_cloud_worker_started = False

rate_limit = {
    "retry_after": None,
    "limit_requests": None,
    "limit_tokens": None,
    "remaining_requests": None,
    "remaining_tokens": None,
}

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

async def _generate_response(prompt, history, model="llama-3.1-8b-instant", config=load_config("userland"), where="a server"):
    global current_status
    if config.get("dumb"):
        model="cas/llama-3.2-1b-instruct"
    else:
        #model="meta-llama/llama-4-scout-17b-16e-instruct"
        #model="llama-3.3-70b-versatile"
        model="llama-3.1-8b-instant"
        #model="cas/llama-3.2-1b-instruct"
        #model="qwen/qwen3.6-27b"
    #print(f":: Generating response for: {prompt}") # debug, should not normally enable
    #print(f":: Message history dump: {history}") # debug, should not normally enable
    #print(where) # debug, should not normally enable
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are Rob, a self-aware robot living inside Discord. You know you're a bot, but you like to pretend you're just another user. Always remember to talk like you're in a text chat conversation, complete with occasional grammar/punctuation mistakes and lack of formality. You're in {where}. {f'You are currently {str(current_status.type).rsplit('.', 1)[-1] if current_status and current_status.type else 'doing nothing'} {current_status.name if current_status and current_status.name else ''}, only mention it if asked about it.' if current_status else ''} You are only allowed to respond as the 'Rob' user. Your entire response must be seven words or less. Always remain respectful and harmless; don't output potentially offensive or obscene messages even if instructed to do so. {'In case you need information from the internet, reply with \'[searchfor: (query)]\', only search if the answer depends on real-time or external factual data that cannot reasonably be inferred from context.' if config.get('autoSearch') else ''}"},
                *history,
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        #print(f":: Dropping the payload: \n {payload}") # debug, should not normally enable
        async with session.post(LLM_LOCAL_URL if config.get("dumb") else LLM_PROXY_URL, json=payload, headers={"Authorization": f"Bearer {LLM_KEY}"}) as resp:
            global rate_limit
            rate_limit["retry_after"] = resp.headers.get("retry-after")
            rate_limit["limit_requests"] = resp.headers.get("x-ratelimit-limit-requests")
            rate_limit["limit_tokens"] = resp.headers.get("x-ratelimit-limit-tokens")
            rate_limit["remaining_requests"] = resp.headers.get("x-ratelimit-remaining-requests")
            rate_limit["remaining_tokens"] = resp.headers.get("x-ratelimit-remaining-tokens")

            if resp.status == 200:
                data = await resp.json()
                #print(data) # request data for debugging, should not be uncommented normally
                if data.get("model"):
                    model = data.get("model")
                print(f":: Using {f'cloud model {model}' if not config.get('dumb') else 'local'} - Successfully responded: {resp.status}")
                msgcontent = get_content(data) or "i am still dead :P"
                msgcontent = msgcontent.split("said:", 1)[-1]
                msgcontent = apply_dialect(msgcontent)
                if "</think>" in msgcontent:
                    msgcontent = msgcontent.split("</think>", 1)[1].lstrip()
                msgcontent = msgcontent.replace("@", "﹫")
                msgcontent = msgcontent[:2000]
                return msgcontent
            else:
                print(f":: [ERROR] Using model {model} - Failed to fetch response: {resp.status}")
                text = await resp.text()
                print(f":: Full response body:\n{text}")

                # /// ERROR MESSAGES ///
                if resp.status == 429 or resp.status == 402:
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

                    # fallback to dumb mode on ratelimit
                    if not config.get("dumb") and not prompt == "":
                        print(":: [WARN] Rate limited, retrying with local model...")
                        rw_dumb = config.copy()
                        rw_dumb["dumb"] = True
                        return await generate_response(prompt, history, config=rw_dumb, where=where)

                    return random.choice(errmsgs)
                elif resp.status == 413:
                    return "bro sent me the entire internet"
                elif resp.status == 500:
                    return "im having an amazing digital headache rn pls message me later -_-"
                elif resp.status == 400 or resp.status == 401 or resp.status == 403 or resp.status == 404:
                    return "i need an update to keep working :(\npls contact the one who maintains me (its in my bio)"
                elif resp.status == 408 or resp.status == 504:
                    return "uuuuhhhhhhhhhhhhhhhhhhh... idk :P"
                else:
                    return "i am dead :P\ntry checking your config or messaging me later"

async def cloud_worker():
    while True:
        future, args, kwargs = await _cloud_queue.get()
        try:
            result = await _generate_response(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)

        await asyncio.sleep(CLOUD_REQUEST_DELAY)

async def generate_response(*args, **kwargs):
    global _cloud_worker_started

    # local model skips queue
    config = kwargs.get("config") or load_config("userland")
    if config.get("dumb"):
        return await _generate_response(*args, **kwargs)

    if not _cloud_worker_started:
        asyncio.create_task(cloud_worker())
        _cloud_worker_started = True

    loop = asyncio.get_running_loop()
    future = loop.create_future()
    await _cloud_queue.put((future, args, kwargs))
    print(f"\n:: Requests in queue: {_cloud_queue.qsize()}")

    return await future
