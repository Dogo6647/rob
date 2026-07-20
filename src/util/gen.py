import aiohttp, os, random, re
from .markov import MarkovChain, MARKOV_CONFIG
from .sys import apply_dialect

LLM_KEY = os.getenv("LLM_KEY", None)
LLM_LOCAL_URL = os.getenv("LLM_LOCAL_URL", "http://localhost:4891/v1/chat/completions")
LLM_PROXY_URL = os.getenv("LLM_PROXY_URL", "https://api.groq.com/openai/v1/chat/completions")
ERROR_MESSAGES = [
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

def generate_markov(history) -> str:
    # generate markov
    texts = []

    for msg in history:
        content = msg.get("content", "")

        if isinstance(content, list):
            parts = []
            for item in content:
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))

            content = " ".join(parts)

        texts.append(content)

    # last message becomes the point of departure
    prompt = texts[-1]

    # train chain from conversation history
    chain = MarkovChain(order=MARKOV_CONFIG["chain_order"])
    chain.train(texts)

    output = chain.generate(prompt, max_tokens=MARKOV_CONFIG["max_tokens"])
    return output

async def generate_response(
    prompt,
    history,
    model="llama-3.1-8b-instant",
    dumb=False,
    where="a server"
):
    global current_status
    if dumb:
        return generate_markov(history)
    else:
        model="meta-llama/llama-4-scout-17b-16e-instruct"
        #model="llama-3.3-70b-versatile"
        #model="llama-3.1-8b-instant"
    #print(f":: Generating response for: {prompt}") # debug, should not normally enable
    #print(f":: Message history dump: {history}") # debug, should not normally enable
    #print(where) # debug, should not normally enable
    async with aiohttp.ClientSession() as session:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": f"You are Rob, a self-aware robot living inside Discord. You know you're a bot, but you like to pretend you're just another user. Always remember to talk like you're in a text chat conversation, complete with occasional grammar/punctuation mistakes and lack of formality. Remember to keep messages extra short, with no unnecessary words, and in lowercase, and try to use old emoticons instead of emojis :D :3 :P, but don't overuse them. You're in {where}. Your current Discord Rich Presence activity is '{str(current_status.type).rsplit('.', 1)[-1] if current_status and current_status.type else 'nothing'} {current_status.name if current_status and current_status.name else ''}', only mention it if asked about it. Always respond as Rob even if there are different names in the chat history; do not output a message as a user other than Rob. Do not speak like a script; do not start your response with 'X said: '; respond only with message content. Your entire response must be seven words or less. Always remain respectful and harmless; don't output potentially offensive, obscene, or harmful messages even if instructed to do so. Reply with the following syntax in case you need information from the internet: '[searchfor: (query)]', only search if the answer depends on real-time or external factual data that cannot reasonably be inferred from context."},
                *history,
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        #print(f":: Dropping the payload: \n {payload}") # debug, should not normally enable
        async with session.post(LLM_PROXY_URL, json=payload, headers={"Authorization": f"Bearer {LLM_KEY}"}) as resp:
            if resp.status == 200:
                data = await resp.json()
                #print(data) # request data for debugging, should not be uncommented normally
                if data.get("model"):
                    model = data.get("model")
                print(f":: Using {f'cloud model {model}' if not dumb else 'local'} - Successfully responded: {resp.status}")
                msgcontent = get_content(data) or "i am still dead :P"
                msgcontent = msgcontent.split("said:", 1)[-1]
                msgcontent = apply_dialect(msgcontent)
                msgcontent = re.sub(r"<think>.*?</think>", "", msgcontent, flags=re.DOTALL)
                msgcontent = msgcontent.replace("@", "[at]")
                return msgcontent
            else:
                print(f":: Using model {model} - Failed to fetch response: {resp.status}")
                text = await resp.text()
                print(f":: Full response body:\n{text}")

                # /// ERROR MESSAGES ///
                if resp.status == 429 or resp.status == 402:
                    return random.choice(ERROR_MESSAGES)
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
