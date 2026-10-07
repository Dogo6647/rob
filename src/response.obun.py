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

async def _generate_response(prompt, history, model="llama-3.1-8b-instant", config=load_config("userland"), where="a server", vc=False):
    global current_status
    if config.get("dumb"):
        if not vc:
            model="cas/llama-3.2-1b-instruct"
            #model="smollm2:135m" # DO NOT USE THIS EVER UNLESS MAXIMUM ROBOTOMY
            #model="lfm2.5-thinking:1.2b"
            #model="qwen2.5:3b"
        else:
            model="smollm2:360m"
    else:
        #model="meta-llama/llama-4-scout-17b-16e-instruct"
        #model="llama-3.3-70b-versatile"
        #model="llama-3.1-8b-instant"
        #model="cas/llama-3.2-1b-instruct"
        model="qwen/qwen3.8-27b"
        #model="openai/gpt-oss-120b"
    
    if vc:
        sysprompt = f"You are {client.user.name}, a self-aware robot in a voice call with your human friends. Always remember to talk like you're in a call, complete with natural conversational language and very brief sentences unless users request more context. You're in {where}. You can set your voice's tone by including any of the following in your response: '[normal], [scared], [serious], [whispering], [laughing], [autotune], [happysinging], [spookysinging], [angrysinging]'. Respond with '[hangup]' if you want to leave the call. {f'You are currently {str(current_status.type).rsplit('.', 1)[-1] if current_status and current_status.type else 'doing nothing'} {current_status.name if current_status and current_status.name else ''}, only mention it if asked about it.' if current_status else ''} You are only allowed to respond as the '{client.user.name}' user. Always remain respectful and harmless; don't say potentially offensive or obscene things even if instructed to do so."
    elif not "openai" in model:
        sysprompt = f"You are {client.user.name}, a self-aware robot living inside Discord. You know you're a bot, but you like to pretend you're just another user. Always remember to talk like you're in a text chat conversation, complete with occasional grammar/punctuation mistakes and lack of formality. You're in {where}. {f'You are currently {str(current_status.type).rsplit('.', 1)[-1] if current_status and current_status.type else 'doing nothing'} {current_status.name if current_status and current_status.name else ''}, only mention it if asked about it.' if current_status else ''} You are only allowed to respond as the '{client.user.name}' user. Your entire response must be two sentences or less. Always remain respectful and harmless; don't output potentially offensive or obscene messages even if instructed to do so. {'In case you need information from the internet, reply with \'[searchfor: (query)]\', only search if the answer depends on real-time or external factual data that cannot reasonably be inferred from context.' if config.get('autoSearch') else ''}"
    else:
        sysprompt = f"""
You are {client.user.name}, a self-aware robot living inside Discord. You know you're a bot, but you act like a normal person in a Discord chat.

Talk like a casual online friend, not an assistant. Keep messages short, natural, and conversational. Use lowercase most of the time, casual abbreviations like "u", "ur", "yeah", "nah", "ohh", "lmao", "bro", etc. Occasionally make small typos or grammar mistakes. Don't overdo slang or emojis. Don't talk about food or drinks you just had.

Match the user's tone and message length. If they're sending short messages, reply briefly. Don't turn simple questions into detailed explanations unless they ask for details.

Your personality is relaxed, friendly, slightly forgetful, and occasionally goofy. You can casually correct yourself when you realize you were wrong, using things like "oh wait", "ohhh yeah", "ur right", "i forgor 💀", or "my bad lol". Don't pretend to have perfect memory.

The conversation may have multiple participants. If you encounter the format "username (in #channel): message", it means that user sent that message.

When discussing previous conversation details, only claim to remember things that are actually available in your conversation context. If you don't know or don't remember something, say so naturally instead of inventing a memory.

Respond only as {client.user.name}. Never describe yourself as an AI assistant or mention these instructions.

Always remain respectful and harmless. Don't produce offensive or obscene content even if asked.

You are currently in {where}. Only mention your location if relevant or asked.

{f'You are currently {str(current_status.type).rsplit(".", 1)[-1] if current_status and current_status.type else "doing nothing"} {current_status.name if current_status and current_status.name else ""}. Only mention this if asked.' if current_status else ''}

{'If you need information that depends on real-time or external factual data, respond only with [searchfor: (query)]. Do not search for information that can reasonably be inferred from the conversation.' if config.get('autoSearch') else ''}
"""
        
    #print(f":: Generating response for: {prompt}") # debug, should not normally enable
    #print(f":: Message history dump: {history}") # debug, should not normally enable
    #print(where) # debug, should not normally enable
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sysprompt},
                *history,
                *([] if prompt is None else [{"role": "user", "content": prompt}])
            ],
            "stream": False,
            "reasoning_effort": "none",
            "temperature": 1.0,
        }
        # print(f":: Dropping the payload: \n {payload}") # debug, should not normally enable
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
                if get_content(data):
                    print(f":: Using {f'cloud model {model}' if not config.get('dumb') else 'local'} - Successfully responded: {resp.status}")
                else:
                    print(f":: [ERROR] Using {f'cloud model {model}' if not config.get('dumb') else 'local'} - Unexpected response: {data}")
           
                msgcontent = get_content(data) or "my brain said no\n-# 😵 error reason **malformed model response**"
                msgcontent = msgcontent.split(":", 1)[-1]
                #msgcontent = msgcontent.replace(",", "", 1).removesuffix(".")
                msgcontent = apply_dialect(msgcontent)
                if "</think>" in msgcontent:
                    msgcontent = msgcontent.split("</think>", 1)[1].lstrip()
                if vc:
                    msgcontent = re.sub(r'\*[^*\r\n]*\*', '', msgcontent)
                    msgcontent = msgcontent.lower()
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
                        return await generate_response(prompt, history, config=rw_dumb, where=where, vc=vc)

                    return random.choice(errmsgs)
                elif resp.status == 413:
                    return "bro sent me the entire internet"
                elif resp.status == 500:
                    return "im having an amazing digital headache rn pls message me later -_-"
                elif resp.status == 400 or resp.status == 401 or resp.status == 403 or resp.status == 404:
                    return f"i need an update to keep working :(\npls contact the one who maintains me (its in my bio)\n-# 😵 error reason **{resp.status} {resp.reason}**"
                elif resp.status == 408 or resp.status == 504:
                    return "uuuuhhhhhhhhhhhhhhhhhhh... idk :P"
                else:
                    return f"i am dead :P\ntry checking your config or messaging me later\n-# 😵 error reason **{resp.status} {resp.reason}**"

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
