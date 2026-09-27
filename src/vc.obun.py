# Voice chat module. This can prob be ripped straight off the codebase and nothing would happen
# except for VC not working, that's why I call it a module.

# also this a large boi

import numpy as np
import discord.ext.voice_recv as voice_recv
from vosk import KaldiRecognizer, Model
discord.opus.load_opus("libopus.so.0") # load the skibidi opus

vosk_model = Model("/usr/share/vosk-models/small-en-us")

#async def disconnect_startup():
#    for vc in client.voice_clients:
#        await vc.disconnect()

TONE_VOICE_MAP = {
    "normal": "Fred",
    "laughing": "Hysterical",
    "happysinging": "GoodNews",
    "spookysinging": "Cellos",
    "angrysinging": "BadNews",
    "autotune": "PipeOrgan",
    "whispering": "Whisper",
    "scared": "Deranged",
    "serious": "Ralph",
}

ENTER_LINES = [
    "Hai!",
    "Hey!",
    "Sup",
    "Alright what we gonna play gamer?",
    "Yo, good to see ya!",
    "Bro told me to hop on VC",
    "Rob.",
    "OK I'm here.",
    "OK",
    "Hello gamers.",
    "Nescoffee",
    "[spookysinging] Spooky scary skeletons",
    "[angrysinging] Your worst nightmare has arrived"
]

DEFAULT_TONE_VOICE = "Fred"
TONE_TAG_RE = re.compile(r"\[([a-zA-Z0-9_ ]+)\]")

MAX_TTS_CHARS = 500
WINTALKER_TIMEOUT_S = 15
VC_EMPTY_TIMEOUT = 2
MAX_RECOGNIZERS_PER_SESSION = 32

VAD_RMS_THRESHOLD = 600
VAD_HANGOVER_S = 0.5

voice_sessions = {}


class StreamingResampler:
    RATIO = 3  # 48000 / 16000

    def __init__(self):
        self._carry = np.array([], dtype=np.float32)

    def push(self, mono_f32: np.ndarray) -> np.ndarray:
        if mono_f32.size == 0:
            return np.array([], dtype=np.int16)

        buf = np.concatenate([self._carry, mono_f32]) if self._carry.size else mono_f32
        n_out = (buf.size - 1) // self.RATIO
        if n_out <= 0:
            self._carry = buf
            return np.array([], dtype=np.int16)

        idx = np.arange(n_out) * self.RATIO
        out = buf[idx]
        consumed = n_out * self.RATIO
        self._carry = buf[consumed:]
        return np.clip(out, -32768, 32767).astype(np.int16)

    def reset(self):
        self._carry = np.array([], dtype=np.float32)


def _pcm_stereo48k_to_mono_f32(pcm_bytes: bytes) -> np.ndarray:
    if not pcm_bytes:
        return np.array([], dtype=np.float32)

    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    if samples.size < 2:
        return np.array([], dtype=np.float32)

    samples = samples[: samples.size - (samples.size % 2)]
    stereo = samples.reshape(-1, 2).astype(np.float32)
    return stereo.mean(axis=1)


class VadState:
    def __init__(self, threshold: float = VAD_RMS_THRESHOLD, hangover_s: float = VAD_HANGOVER_S):
        self.threshold = threshold
        self.hangover_s = hangover_s
        self.speaking = False
        self._below_since = None

    @staticmethod
    def _rms(samples_i16: np.ndarray) -> float:
        if samples_i16.size == 0:
            return 0.0
        f = samples_i16.astype(np.float32)
        return float(np.sqrt(np.mean(f * f)))

    def update(self, samples_i16: np.ndarray, now: float):
        if samples_i16.size == 0:
            if self.speaking:
                if self._below_since is None:
                    self._below_since = now
                elif now - self._below_since >= self.hangover_s:
                    self.speaking = False
                    self._below_since = None
                    return "end"
                return "continue"
            return "silent"

        level = self._rms(samples_i16)
        loud = level >= self.threshold

        if loud:
            self._below_since = None
            if not self.speaking:
                self.speaking = True
                return "start"
            return "continue"

        if self.speaking:
            if self._below_since is None:
                self._below_since = now
            if now - self._below_since >= self.hangover_s:
                self.speaking = False
                self._below_since = None
                return "end"
            return "continue"

        return "silent"

    def reset(self):
        self.speaking = False
        self._below_since = None


class VoiceReceiver(voice_recv.AudioSink):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.closed = False

    def wants_opus(self):
        return False

    def write(self, user, data):
        if self.closed or user is None or self.session is None:
            return

        try:
            self.session["raw_queue"].put_nowait((user.id, data.pcm))
        except asyncio.QueueFull:
            pass
        except Exception as e:
            print(f":: [ERROR] In voice channel: {e}")

    def cleanup(self):
        self.closed = True
        self.session = None


def _normalize_member_id(user):
    return getattr(user, "id", user)


async def join_user_voice(user, guild):
    member = user if isinstance(user, discord.Member) else None
    if member is None:
        user_id = _normalize_member_id(user)
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return False

    if member is None or member.voice is None or member.voice.channel is None:
        return False

    channel = member.voice.channel
    vc = guild.voice_client
    if vc and vc.is_connected():
        if vc.channel.id != channel.id:
            await vc.move_to(channel)
        elif guild.id in voice_sessions:
            # Already listening
            return True
    else:
        vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
    await _start_voice_session(guild, vc)
    return True


async def leave_voice(guild):
    session = voice_sessions.pop(guild.id, None)
    if session:
        for task_key in ("watchdog_task", "consumer_task"):
            task = session.get(task_key)
            if task:
                task.cancel()

        for task in list(session.get("pending_utterances", ())):
            task.cancel()

        receiver = session.get("receiver")
        if receiver:
            receiver.cleanup()

    vc = guild.voice_client
    if vc and vc.is_connected():
        if vc.is_playing():
            vc.stop()
        await vc.disconnect(force=True)
        return True

    return False

def _stop_voice_receiver(vc):
    try:
        vc.stop_listening()
    except Exception:
        pass

async def _start_voice_session(guild, vc):
    old = voice_sessions.get(guild.id)
    if old:
        old_receiver = old.get("receiver")
        if old_receiver:
            old_receiver.cleanup()
        for task_key in ("watchdog_task", "consumer_task"):
            task = old.get(task_key)
            if task:
                task.cancel()
    
    _stop_voice_receiver(vc)

    session = {
        "vc": vc,
        "raw_queue": asyncio.Queue(maxsize=256),
        "recognizers": {},
        "resamplers": {},
        "vad_states": {},
        "speaker": None,
        "last_speaker": None,
        "rob_talking": False,
        "lock": asyncio.Lock(),
        "last_nonempty": time.monotonic(),
        "pending_utterances": set(),
    }
    
    receiver = VoiceReceiver(session)
    session["receiver"] = receiver
    voice_sessions[guild.id] = session
    vc.listen(receiver)

    loop = asyncio.get_running_loop()
    await asyncio.sleep(1)
    await _speak(guild, session, random.choice(ENTER_LINES))
    session["consumer_task"] = loop.create_task(_consume_audio_loop(guild, session))
    session["watchdog_task"] = loop.create_task(_empty_channel_watchdog(guild))


def _get_recognizer(session, user_id):
    recognizer = session["recognizers"].get(user_id)
    if recognizer is not None:
        return recognizer

    if len(session["recognizers"]) >= MAX_RECOGNIZERS_PER_SESSION:
        oldest_id = next(iter(session["recognizers"]))
        session["recognizers"].pop(oldest_id, None)
        session["resamplers"].pop(oldest_id, None)
        session["vad_states"].pop(oldest_id, None)

    recognizer = KaldiRecognizer(vosk_model, 16000)
    session["recognizers"][user_id] = recognizer
    return recognizer


def _get_resampler(session, user_id) -> StreamingResampler:
    resampler = session["resamplers"].get(user_id)
    if resampler is None:
        resampler = StreamingResampler()
        session["resamplers"][user_id] = resampler
    return resampler


def _get_vad(session, user_id) -> VadState:
    vad = session["vad_states"].get(user_id)
    if vad is None:
        vad = VadState()
        session["vad_states"][user_id] = vad
    return vad


async def _consume_audio_loop(guild, session):
    print(":: Let's get this started!")

    while voice_sessions.get(guild.id) is session:
        try:
            user_id, pcm = await session["raw_queue"].get()
        except asyncio.CancelledError:
            return

        vc = session["vc"]
        if user_id == vc.guild.me.id:
            continue

        current = session["speaker"]
        if current and current != user_id:
            continue

        mono_f32 = _pcm_stereo48k_to_mono_f32(pcm)
        if mono_f32.size == 0:
            continue

        resampler = _get_resampler(session, user_id)
        pcm16 = resampler.push(mono_f32)
        if pcm16.size == 0:
            continue

        vad = _get_vad(session, user_id)
        now = time.monotonic()
        event = vad.update(pcm16, now)

        if event == "silent":
            # nothing being said
            continue

        recognizer = _get_recognizer(session, user_id)

        if event == "start":
            if vc.is_playing() and session["rob_talking"] and user_id == session["last_speaker"]:
                vc.stop_playing()

            if session["speaker"] is None:
                session["speaker"] = user_id
            try:
                recognizer.Reset()
            except Exception as e:
                print(f":: [ERROR] In voice chat VAD: Reset failed: {e}")

        # "start" and "continue" both mean we're currently inside an utterance, so feed this chunk to the recognizer.
        if event in ("start", "continue"):
            audio = pcm16.tobytes()
            try:
                recognizer.AcceptWaveform(audio)
            except Exception as e:
                print(f":: [ERROR] In voice chat vosk: {e}")
            continue

        try:
            result = json.loads(recognizer.FinalResult())
        except Exception as e:
            print(f":: [ERROR] In voice chat vosk: {e}")
            result = {}

        text = (result.get("text") or "").strip()

        if not text:
            # free up the speaker slot for other people
            if session["speaker"] == user_id:
                session["speaker"] = None
            continue

        session["last_speaker"] = user_id
        task = asyncio.create_task(_handle_utterance(guild, session, user_id, text))
        session["pending_utterances"].add(task)
        task.add_done_callback(lambda t: session["pending_utterances"].discard(t))


async def _handle_utterance(guild, session, user_id, text):
    async with session["lock"]:
        if voice_sessions.get(guild.id) is not session:
            return

        member = guild.get_member(user_id)
        username = member.display_name if member else f"user {user_id}"

        history = guild_vc_histories[guild.id]
        history.append({"role": "user", "content": f"{username}: {text}"})

        session["rob_talking"] = True

        try:
            response = await generate_response(
                "Respond as Rob, out loud, to what was just said in voice chat.",
                history,
                load_config(guild.id).get("model"),
                load_config(guild.id),
                f"the {guild.name} server",
                vc=True,
            )

            history.append({"role": "assistant", "content": f"Rob: {response}"})
            await _speak(guild, session, response)

        except asyncio.CancelledError:
            raise
        except Exception:
            pass

        finally:
            if voice_sessions.get(guild.id) is session:
                session["rob_talking"] = False
                session["speaker"] = None
                for r in session["recognizers"].values():
                    try:
                        r.Reset()
                    except Exception:
                        pass
                for v in session["vad_states"].values():
                    v.reset()


def _extract_tags(response):
    tags = [m.group(1).lower() for m in TONE_TAG_RE.finditer(response)]
    text = TONE_TAG_RE.sub("", response)
    return re.sub(r"\s+", " ", text).strip(), tags


def _resolve_voice(tags):
    for tag in tags:
        if tag in TONE_VOICE_MAP:
            return TONE_VOICE_MAP[tag]
    return DEFAULT_TONE_VOICE


async def _run_wintalker(voice_name: str, text: str, out_path: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "wintalker", "-v", voice_name, text, "-o", out_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=WINTALKER_TIMEOUT_S)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return False

        if proc.returncode != 0:
            return False

        return os.path.exists(out_path)

    except FileNotFoundError:
        print(":: [ERROR] Wintalker executable not found")
        return False
    except Exception:
        print(":: [ERROR] Could not run wintalker")
        return False


async def _speak(guild, session, response):
    vc = session["vc"]
    clean, tags = _extract_tags(response)

    if not clean:
        return

    if len(clean) > MAX_TTS_CHARS:
        clean = clean[:MAX_TTS_CHARS].rsplit(" ", 1)[0] or clean[:MAX_TTS_CHARS]

    filename = os.path.join(VC_TMP_DIR, f"{random.randint(10**9, 10**10)}.wav")

    ok = await _run_wintalker(_resolve_voice(tags), clean, filename)
    if not ok:
        return

    if voice_sessions.get(guild.id) is not session or not vc.is_connected():
        _safe_remove(filename)
        return

    finished = asyncio.Event()
    loop = asyncio.get_running_loop()

    def after(error):
        loop.call_soon_threadsafe(finished.set)

    try:
        vc.play(discord.FFmpegPCMAudio(filename), after=after)
    except Exception as e:
        print(f":: [ERROR] In voice chat: Failed to start playback: {e}")
        _safe_remove(filename)
        return

    await finished.wait()
    _safe_remove(filename)

    if "hangup" in tags:
        await leave_voice(guild)
        return


def _safe_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


async def _empty_channel_watchdog(guild):
    try:
        while True:
            await asyncio.sleep(1)

            session = voice_sessions.get(guild.id)
            if not session:
                return

            vc = session["vc"]
            if not vc.is_connected():
                return

            humans = [m for m in vc.channel.members if not m.bot]

            if humans:
                session["last_nonempty"] = time.monotonic()
                continue

            if time.monotonic() - session["last_nonempty"] >= VC_EMPTY_TIMEOUT:
                await leave_voice(guild)
                return

    except asyncio.CancelledError:
        pass
