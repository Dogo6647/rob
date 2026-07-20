from flask import Flask, request, jsonify
from collections import defaultdict
import random
import re
import uuid

app = Flask(__name__)

MARKOV_CONFIG = {
    "chain_order": 2, # n-gram size
    "max_tokens": 60, # max generated tokens
    "temperature": 1.0, # randomness scaling
    "fallback_to_random": True
}

# --- Tokenization ---
TOKEN_REGEX = re.compile(r"\w+|[^\w\s]")

def tokenize(text):
    return TOKEN_REGEX.findall(text.lower())

def untokenize(tokens):
    out = []

    for token in tokens:
        if token in ".,!?;:":
            if out:
                out[-1] += token
            else:
                out.append(token)
        else:
            out.append(token)

    return " ".join(out)


# --- Markov ---
class MarkovChain:
    def __init__(self, order=2):
        self.order = order
        self.chain = defaultdict(list)
        self.starts = []

    def train(self, texts):
        for text in texts:
            tokens = tokenize(text)

            if len(tokens) < self.order + 1:
                continue

            self.starts.append(tuple(tokens[:self.order]))

            for i in range(len(tokens) - self.order):
                key = tuple(tokens[i:i + self.order])
                next_token = tokens[i + self.order]
                self.chain[key].append(next_token)

    def find_best_seed(self, prompt):
        prompt_tokens = tokenize(prompt)

        # try longest matching suffix first
        for size in range(self.order, 0, -1):
            if len(prompt_tokens) < size:
                continue

            suffix = tuple(prompt_tokens[-size:])

            for key in self.chain.keys():
                if key[:size] == suffix:
                    return key

        return random.choice(self.starts) if self.starts else None

    def sample_next(self, choices):
        if not choices:
            return None

        # meh temperature support
        counts = defaultdict(int)

        for token in choices:
            counts[token] += 1

        weighted = []

        for token, count in counts.items():
            weight = count ** (1.0 / max(MARKOV_CONFIG["temperature"], 0.01))
            weighted.append((token, weight))

        total = sum(w for _, w in weighted)
        r = random.uniform(0, total)

        upto = 0

        for token, weight in weighted:
            upto += weight
            if upto >= r:
                return token

        return random.choice(choices)

    def generate(self, prompt, max_tokens=50):
        seed = self.find_best_seed(prompt)

        if not seed:
            return "hehe whar"

        generated = list(seed)

        for _ in range(max_tokens):
            key = tuple(generated[-self.order:])

            next_choices = self.chain.get(key)

            if not next_choices:
                break

            next_token = self.sample_next(next_choices)
            generated.append(next_token)

        return untokenize(generated)
