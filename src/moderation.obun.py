RMPL_DIR = "src/moderation"
MOD_PERMS = ("moderate_members", "kick_members", "ban_members", "manage_messages")
MOD_TIMEOUTS = [60, 300, 600, 3600, 86400, 604800]
MOD_RETENTION = 3600
MOD_GROUP_WINDOW = 300
MOD_STAFF_HINTS = ["staff", "moderator", "admin", "mod", "log"]
MOD_CUSTOM_LIMIT = 4096
MOD_REGEX_MAX = 100
MOD_TIMEOUT_MAX = 28 * 86400 # discord's own timeout cap
MOD_DM_TIMEOUT = 5
_MOD_UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 30 * 86400, "year": 365 * 86400}
_MOD_UNIT_RX = "|".join(_MOD_UNITS)

from re import _parser as _sre_parse, _constants as _sre_const

@dataclass
class ModStep:
    kind: str
    same: bool = False
    terms: list = field(default_factory=list)
    gap: int | None = None
    delay: float | None = None
    channels: int = 0
    younger: bool = True
    age: float | None = None
    attachments: list = field(default_factory=list)
@dataclass
class ModAction:
    kind: str
    count: int | None = None
    text: str = ""
    seconds: int = 0
@dataclass
class ModStage:
    steps: list
    actions: list
@dataclass
class ModRule:
    id: str
    file: str
    description: str
    stages: list
    scope: tuple | None = None
    username: re.Pattern | None = None
@dataclass
class ModFile:
    name: str
    description: str
    rules: list
    source: str = ""
    custom: bool = False
@dataclass
class ModEvent:
    kind: str
    time: float
    message: discord.Message | None = None
    channel_id: int = 0
    channel_name: str = ""
    content: str = ""
    key: str = ""
    mentions: frozenset = frozenset()
    consumed: set = field(default_factory=set)
    files: tuple = ()
    created: float = 0.0


def _mod_terms(text):
    if not re.fullmatch(r'\s*"[^"]+"(?:\s+(?:and|or)\s+"[^"]+")*\s*', text):
        raise ValueError(f"invalid term list {text}")
    groups = [[]]
    for quoted, word in re.findall(r'"([^"]+)"|\b(or)\b', text):
        if word:
            groups.append([])
        else:
            groups[-1].append(quoted.lower())
    return groups

def _mod_subpatterns(av):
    if isinstance(av, _sre_parse.SubPattern):
        yield av
    elif isinstance(av, (tuple, list)):
        for x in av:
            yield from _mod_subpatterns(x)

def _mod_regex_nested(node, repeating=False):
    for op, av in node.data:
        if op in (_sre_const.MAX_REPEAT, _sre_const.MIN_REPEAT):
            _, hi, sub = av
            multi = hi > 1
            if repeating and multi:
                return True
            if _mod_regex_nested(sub, repeating or multi):
                return True
        elif any(_mod_regex_nested(sub, repeating) for sub in _mod_subpatterns(av)):
            return True
    return False

def _mod_regex(pattern):
    if len(pattern) > MOD_REGEX_MAX:
        raise ValueError(f"regex is longer than {MOD_REGEX_MAX} characters")
    try:
        rx = re.compile(pattern, re.IGNORECASE)
        tree = _sre_parse.parse(pattern, re.IGNORECASE)
    except (re.error, RecursionError) as e:
        raise ValueError(f"invalid regex ({e})")
    if _mod_regex_nested(tree):
        raise ValueError("regex has a repeat inside another repeat like (a+)+ which is too slow to run safely")
    return rx

_MOD_ATTACH_REQ = re.compile(
    r"(?:(more than|at least|fewer than|less than|at most|exactly) )?(\d+) "
    r"(images?|videos?|audios?|files?|attachments?|\.[a-z0-9]+)"
)
_MOD_ATTACH_OPS = {
    None: ">=", "at least": ">=", "more than": ">",
    "fewer than": "<", "less than": "<", "at most": "<=", "exactly": "==",
}

def _mod_attachments(text):
    reqs = []
    for part in re.split(r"\s+and\s+", text.strip()):
        m = _MOD_ATTACH_REQ.fullmatch(part)
        if not m:
            raise ValueError(f"invalid attachment condition '{part}'")
        kind = m.group(3)
        if not kind.startswith("."):
            kind = kind.rstrip("s") if kind != "audios" else "audio"
            kind = {"attachment": "file"}.get(kind, kind)
        reqs.append((_MOD_ATTACH_OPS[m.group(1)], int(m.group(2)), kind))
    return reqs

_MOD_EXT_KINDS = {
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".heic", ".avif", ".svg"},
    "video": {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"},
    "audio": {".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac", ".opus"},
}

def _mod_attachment_kind(attachment):
    ctype = (attachment.content_type or "").split(";")[0].lower()
    ext = os.path.splitext(attachment.filename.lower())[1]
    for kind, exts in _MOD_EXT_KINDS.items():
        if ctype.startswith(kind + "/") or ext in exts:
            return kind, ext
    return "other", ext

def _mod_parse_step(line):
    step = ModStep("anything")
    m = re.fullmatch(r"(?:less than|within) (\d+(?:\.\d+)?) (message|second|minute|hour)s?(?: later)?\s*;\s*(.+)", line)
    if m:
        num, unit, line = float(m.group(1)), m.group(2), m.group(3)
        if unit == "message":
            step.gap = int(num)
        else:
            step.delay = num * {"second": 1, "minute": 60, "hour": 3600}[unit]

    if m := re.fullmatch(rf"joins(?: while (younger|older) than (\d+(?:\.\d+)?) ({_MOD_UNIT_RX})s?)?", line):
        step.kind = "joins"
        if m.group(1):
            step.younger = m.group(1) == "younger"
            step.age = float(m.group(2)) * _MOD_UNITS[m.group(3)]
    elif line == "sends anything":
        pass
    elif m := re.fullmatch(r"sends message with (.+)", line):
        step.kind, step.attachments = "attachments", _mod_attachments(m.group(1))
    elif m := re.fullmatch(r"sends the same(?: message)?(?: in more than (\d+) different channels)?", line):
        if m.group(1):
            step.kind, step.channels = "group", int(m.group(1))
        else:
            step.same = True
    elif m := re.fullmatch(r"sends message containing (.+)", line):
        step.kind, step.terms = "contains", _mod_terms(m.group(1))
    elif m := re.fullmatch(r"mentions (.+)", line):
        if m.group(1) == "the same":
            step.kind, step.same = "mentions", True
        elif re.fullmatch(r"(?:@everyone|@here|anyone)(?: or (?:@everyone|@here|anyone))*", m.group(1)):
            step.kind, step.terms = "mentions", re.findall(r"@everyone|@here|anyone", m.group(1))
        else:
            raise ValueError(f"unknown step '{line}'")
    else:
        raise ValueError(f"unknown step '{line}'")
    return step

_MOD_ACTIONS = [
    ("timeout", re.compile(r"timeout incremental\b")),
    ("timeout_for", re.compile(rf"timeout for (\d+) ({_MOD_UNIT_RX})s?\b")),
    ("kick", re.compile(r"kick\b")),
    ("ban", re.compile(r"ban\b")),
    ("delete", re.compile(r"delete (?:(all) messages|last (?:(\d+) )?messages?)")),
    ("warn", re.compile(r'warn "((?:[^"\\]|\\.)*)"')),
    ("inform", re.compile(r'inform "((?:[^"\\]|\\.)*)"')),
]

def _mod_parse_actions(line):
    actions, pos = [], 0
    while pos < len(line):
        for kind, rx in _MOD_ACTIONS:
            m = rx.match(line, pos)
            if m:
                break
        else:
            raise ValueError(f"unknown action '{line[pos:]}'")
        action = ModAction(kind)
        if kind == "delete":
            action.count = None if m.group(1) else int(m.group(2) or 1)
        elif kind in ("warn", "inform"):
            action.text = m.group(1).replace('\\"', '"')
        elif kind == "timeout_for":
            action.seconds = int(m.group(1)) * _MOD_UNITS[m.group(2)]
            if not 0 < action.seconds <= MOD_TIMEOUT_MAX:
                raise ValueError("a timeout must be between 1 second and 28 days")
        actions.append(action)
        pos = m.end()
        if pos < len(line):
            sep = re.compile(r"\s*(?:,|\band\b)\s*").match(line, pos)
            if not sep:
                raise ValueError(f"unexpected '{line[pos:]}'")
            pos = sep.end()
    return actions

def _mod_make_stage(steps, actions, first):
    if first and steps[0].same:
        raise ValueError("the first step can't be 'the same'")
    if any(s.kind == "group" for s in steps) and (len(steps) > 1 or steps[0].gap is not None):
        raise ValueError("a channel-spread step must be the only step in its stage and can only use a time window")
    return ModStage(steps, actions)

def _mod_parse_rule(rule_id, file, description, block):
    scope, username, stages = None, None, []
    steps, actions = [], []
    for line in (l.strip() for l in block.split("\n")):
        if not line or line.startswith("#"):
            continue
        if m := re.fullmatch(r"in channel (not )?containing (.+)", line):
            scope = (bool(m.group(1)), _mod_terms(m.group(2)))
        elif m := re.fullmatch(r"username matches (.+)", line):
            if username:
                raise ValueError("only one username condition is allowed per rule")
            username = _mod_regex(m.group(1))
        elif re.match(r"(?:timeout|kick|ban|delete|warn|inform)\b", line):
            if not steps:
                raise ValueError("an action needs at least one step before it")
            actions += _mod_parse_actions(line)
        else:
            if actions: # a step after actions starts the next stage
                stages.append(_mod_make_stage(steps, actions, not stages))
                steps, actions = [], []
            steps.append(_mod_parse_step(line))
    if steps and actions:
        stages.append(_mod_make_stage(steps, actions, not stages))
        steps, actions = [], []
    if steps or not stages:
        raise ValueError("needs at least one step and one action, and must end with an action")
    return ModRule(rule_id, file, description, stages, scope, username)

def _mod_parse_file(name, text, custom=False, strict=False):
    text = text.replace("\r\n", "\n").strip()
    comment = []
    for line in text.split("\n"):
        if not line.startswith("#"):
            break
        comment.append(line.lstrip("#").strip())
    description = " ".join(comment) or "no description"

    rules = []
    for n, block in enumerate(re.split(r"\n\s*\n", text)):
        if all(not l.strip() or l.strip().startswith("#") for l in block.split("\n")):
            continue
        try:
            rules.append(_mod_parse_rule(f"{name}:{n}", name, description, block))
        except ValueError as e:
            if strict:
                raise ValueError(f"rule {n + 1}: {e}")
            print(f":: [WARN] {name} rule {n + 1} skipped, {e}")
    if strict and not rules:
        raise ValueError("there are no rules in there")
    return ModFile(name, description, rules, text, custom)

def moderation_load_rules():
    found = {}
    if not os.path.isdir(RMPL_DIR):
        return found
    for filename in sorted(os.listdir(RMPL_DIR)):
        if not filename.endswith(".rmpl"):
            continue
        with open(os.path.join(RMPL_DIR, filename), encoding="utf-8") as f:
            text = f.read()
        parts = re.split(r"[_\-\s]+", filename[:-5])
        name = parts[0][:1].lower() + parts[0][1:] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
        found[name] = _mod_parse_file(name, text)
    return found

moderation_rules = moderation_load_rules()


_mod_events = {}
_mod_offenses = {}
_mod_custom = {}
_mod_tasks = set()
_mod_progress = {} # (guild_id, user_id, rule_id) -> {"stage", "at", "chain", "deleted"}

def _mod_spawn(coro):
    task = asyncio.create_task(coro)
    _mod_tasks.add(task)
    task.add_done_callback(_mod_tasks.discard)

def _mod_message_event(message):
    norm = " ".join(message.content.lower().split())
    attachments = ",".join(f"{a.filename}:{a.size}" for a in message.attachments)
    mentions = {f"u{u.id}" for u in message.mentions if u.id != message.author.id and not u.bot}
    mentions |= {f"r{r.id}" for r in message.role_mentions}
    mentions |= {m for m in ("@everyone", "@here") if m in message.content}
    return ModEvent(
        "message", message.created_at.timestamp(), message,
        message.channel.id, getattr(message.channel, "name", ""),
        message.content.lower(), f"{norm}\x00{attachments}" if norm or attachments else "",
        frozenset(mentions),
        files=tuple(_mod_attachment_kind(a) for a in message.attachments)
    )

def _mod_record(guild_id, user_id, event):
    dq = _mod_events.setdefault((guild_id, user_id), deque(maxlen=100))
    cutoff = time.time() - MOD_RETENTION
    while dq and dq[0].time < cutoff:
        dq.popleft()
    dq.append(event)
    if len(_mod_events) > 2000:
        for k in [k for k, v in _mod_events.items() if v[-1].time < cutoff]:
            del _mod_events[k]
    return list(dq)

def _mod_scope_ok(rule, ev):
    if rule.scope is None:
        return True
    negate, groups = rule.scope
    name = ev.channel_name.lower()
    return any(all(t in name for t in g) for g in groups) != negate

_MOD_COMPARE = {
    ">=": lambda a, b: a >= b, ">": lambda a, b: a > b,
    "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b,
}

def _mod_step_ok(rule, step, ev):
    if step.kind == "joins":
        if ev.kind != "join":
            return False
        if step.age is None:
            return True
        age = ev.time - ev.created
        return age < step.age if step.younger else age > step.age
    if ev.kind != "message" or not _mod_scope_ok(rule, ev):
        return False
    if step.kind == "attachments":
        for op, number, kind in step.attachments:
            if kind == "file":
                have = len(ev.files)
            elif kind.startswith("."):
                have = sum(ext == kind for _, ext in ev.files)
            else:
                have = sum(k == kind for k, _ in ev.files)
            if not _MOD_COMPARE[op](have, number):
                return False
        return True
    if step.kind == "contains":
        return any(all(t in ev.content for t in g) for g in step.terms)
    if step.kind == "mentions":
        if step.same or "anyone" in step.terms:
            return bool(ev.mentions)
        return any(t in ev.mentions for t in step.terms)
    return True

def _mod_same(step, prev, ev):
    if step.kind == "mentions":
        return bool(prev.mentions & ev.mentions)
    return bool(prev.key) and prev.key == ev.key

def _mod_chain(rule, steps, i, events, idx, prior):
    step, ev = steps[i], events[idx]
    if not _mod_step_ok(rule, step, ev):
        return None
    if i == 0:
        if not prior:
            return [ev]
        anchor = prior[-1]
        if step.gap is None:
            if idx != 0:
                return None
        elif sum(e.kind == "message" for e in events[:idx + 1]) > step.gap:
            return None
        if step.delay is not None and ev.time - anchor.time >= step.delay:
            return None
        if step.same and not _mod_same(step, anchor, ev):
            return None
        return [ev]
    seen = 0
    for j in range(idx - 1, -1, -1):
        if events[j + 1].kind == "message":
            seen += 1
        if step.gap is None and j < idx - 1:
            break
        if step.gap is not None and seen > step.gap:
            break
        prev = events[j]
        if step.delay is not None and ev.time - prev.time >= step.delay:
            continue
        if step.same and not _mod_same(step, prev, ev):
            continue
        chain = _mod_chain(rule, steps, i - 1, events, j, prior)
        if chain:
            return chain + [ev]
    return None

def _mod_group(rule, step, events):
    cur = events[-1]
    if cur.kind != "message" or not cur.key or not _mod_scope_ok(rule, cur):
        return None
    window = step.delay or MOD_GROUP_WINDOW
    group = [
        e for e in events
        if e.kind == "message" and e.key == cur.key and cur.time - e.time <= window and _mod_scope_ok(rule, e)
    ]
    return group if len({e.channel_id for e in group}) > step.channels else None

def _mod_match(rule, stage, events, prior):
    for i in range(len(events) - 1, -1, -1):
        if rule.id in events[i].consumed:
            events = events[i + 1:]
            break
    if not events:
        return None
    if stage.steps[0].kind == "group":
        return _mod_group(rule, stage.steps[0], events)
    return _mod_chain(rule, stage.steps, len(stage.steps) - 1, events, len(events) - 1, prior)


def _mod_custom_path(guild_id):
    return os.path.join(CONFIG_DIR, f"{guild_id}.rules.json")

def moderation_custom(guild_id):
    # loaded from disk then cached
    data = _mod_custom.get(guild_id)
    if data is None:
        try:
            with open(_mod_custom_path(guild_id), "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError):
            raw = {}
        data = {}
        for name, text in raw.items():
            try:
                data[name] = _mod_parse_file(name, text, custom=True, strict=True)
            except ValueError as e:
                print(f":: [WARN] custom rule {name} of {guild_id} skipped, {e}")
        _mod_custom[guild_id] = data
    return data

def moderation_custom_save(guild_id, data):
    _mod_custom[guild_id] = data
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(_mod_custom_path(guild_id), "w", encoding="utf-8") as f:
        json.dump({name: file.source for name, file in data.items()}, f, indent=4)

def moderation_custom_size(guild_id):
    return sum(len(f.source.encode("utf-8")) for f in moderation_custom(guild_id).values())

def moderation_rules_for(guild_id):
    return {**moderation_custom(guild_id), **moderation_rules}

def moderation_find_rule(guild_id, name):
    wanted = name.lower()
    return next((f for n, f in moderation_rules_for(guild_id).items() if n.lower() == wanted), None)

def _mod_active(guild_id, config):
    rules = moderation_rules_for(guild_id)
    return [r for n in config.get("moderationRules", []) if n in rules for r in rules[n].rules]

def _mod_missing(guild):
    options = [
        [] if r.permissions.administrator else [p for p in MOD_PERMS if not getattr(r.permissions, p)]
        for r in guild.me.roles
    ]
    return min(options, key=len, default=list(MOD_PERMS))

def moderation_enabled(guild):
    return not _mod_missing(guild)

def _mod_actionable(member):
    guild = member.guild
    return not (
        member.guild_permissions.administrator
        or member.id == guild.owner_id
        or member.top_role >= guild.me.top_role
    )

def _mod_offense_data(guild_id):
    data = _mod_offenses.get(guild_id)
    if data is None:
        try:
            with open(os.path.join(CONFIG_DIR, f"{guild_id}.offenses.json"), "r") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        _mod_offenses[guild_id] = data
    return data

def _mod_offense_save(guild_id):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(os.path.join(CONFIG_DIR, f"{guild_id}.offenses.json"), "w") as f:
        json.dump(_mod_offenses[guild_id], f)

def _mod_bump(guild_id, user_id):
    data = _mod_offense_data(guild_id)
    data[str(user_id)] = data.get(str(user_id), 0) + 1
    _mod_offense_save(guild_id)
    return data[str(user_id)]

def moderation_reset(guild_id, user_id):
    # forgets a user's offenses
    data = _mod_offense_data(guild_id)
    count = data.pop(str(user_id), 0)
    if count:
        _mod_offense_save(guild_id)
    return count

def _mod_duration(seconds):
    parts = []
    for unit in ("week", "day", "hour", "minute", "second"):
        n, seconds = divmod(seconds, _MOD_UNITS[unit])
        if n:
            parts.append(f"{n} {unit}{'s' if n != 1 else ''}")
    return " ".join(parts) or "0 seconds"


async def _mod_dm_removal(member, rule, verb, extra=""):
    guild = member.guild
    lines = [f"you were **{verb}** from **{guild.name}** by rob's automated moderation."]
    if extra:
        lines.append(extra)
    lines.append(f"rule triggered: `{rule.file}`" + ("" if rule.description == "no description" else f" - {rule.description}"))
    lines.append("if you think this was a mistake, please contact the server's staff and provide them with these details.")
    try:
        await asyncio.wait_for(member.send("\n".join(lines)), MOD_DM_TIMEOUT)
    except (discord.HTTPException, asyncio.TimeoutError):
        pass

async def _mod_ban(member, rule, reason, extra=""):
    await _mod_dm_removal(member, rule, "banned", extra)
    await member.ban(reason=reason)
    moderation_reset(member.guild.id, member.id)

async def _mod_execute(member, rule, actions, chain, deleted, config):
    guild = member.guild
    messages = [e for e in chain if e.message]
    channel = messages[-1].message.channel if messages else get_mail_channel(guild, config)
    reason = f"Rob moderation ({rule.file})"
    results, removed = [], False

    for action in actions:
        try:
            if action.kind == "timeout":
                count = _mod_bump(guild.id, member.id)
                if count > len(MOD_TIMEOUTS):
                    await _mod_ban(member, rule, reason, f"this was offense {count}, repeated offenses end in a ban.")
                    results.append(f"banned (offense {count})")
                    removed = True
                else:
                    seconds = MOD_TIMEOUTS[count - 1]
                    await member.timeout(timedelta(seconds=seconds), reason=reason)
                    results.append(f"timed out for {_mod_duration(seconds)} (offense {count})")
            elif action.kind == "timeout_for":
                await member.timeout(timedelta(seconds=action.seconds), reason=reason)
                results.append(f"timed out for {_mod_duration(action.seconds)}")
            elif action.kind == "kick":
                await _mod_dm_removal(member, rule, "kicked")
                await member.kick(reason=reason)
                results.append("kicked")
                removed = True
            elif action.kind == "ban":
                await _mod_ban(member, rule, reason)
                results.append("banned")
                removed = True
            elif action.kind == "delete":
                targets = [e.message for e in messages if e.message.id not in deleted]
                if action.count is not None:
                    targets = targets[-action.count:]
                done = await asyncio.gather(*(m.delete() for m in targets), return_exceptions=True)
                n = 0
                for m, r in zip(targets, done):
                    if not isinstance(r, Exception):
                        deleted.add(m.id)
                        n += 1
                results.append(f"deleted {n} message{'s' if n != 1 else ''}")
            elif action.kind == "warn":
                await channel.send(
                    f"{member.mention} {action.text}",
                    allowed_mentions=discord.AllowedMentions(users=[member])
                )
                results.append("warned")
            elif action.kind == "inform":
                # like warn but doesn't create an incident
                try:
                    await channel.send(f"{member.mention} {action.text}",allowed_mentions=discord.AllowedMentions(users=[member]))
                except Exception as e:
                    print(f":: [WARN] Couldn't inform {member.id} in {guild.id}: {e}")
        except Exception as e:
            results.append(f"failed to {action.kind} ({getattr(e, 'status', type(e).__name__)})")
    return results, removed

async def _mod_notify(member, rule, matched, results, config):
    guild = member.guild
    channel = get_moderation_channel(guild, config)
    if not channel:
        return

    caught = [
        "- joined the server" if e.kind == "join" else f"- in #{e.channel_name}: {e.message.content[:200] or '[no text]'}"
        for e in matched
    ]
    prompt = (
        "You have just taken a moderation action. Summarize the incident for the server's staff, covering what the user did "
        "and what was done about it. Do not use colons or @ mentions.\n\n"
        f"Rule {rule.file} ({rule.description})\n"
        f"User {member.name}\n"
        "What they did\n" + "\n".join(caught) + "\n"
        "Actions taken\n" + "; ".join(results)
    )
    try:
        summary = (await generate_response(prompt, [], config.get("model"), config, f"the {guild.name} server's staff channel")).strip()
    except Exception as e:
        print(f":: [WARN] Incident summary failed: {e}")
        summary = f"{member.name} triggered {rule.file}."

    last = next((e for e in reversed(matched) if e.message), None)
    embed = discord.Embed(title="🚨 moderation incident", description=summary, color=0xE74C3C)
    embed.add_field(name="user", value=f"{member.mention} (`{member.id}`)")
    embed.add_field(name="rule", value=f"`{rule.file}`")
    if last:
        embed.add_field(name="channel", value=last.message.channel.mention)
    embed.add_field(name="actions", value="\n".join(f"• {r}" for r in results), inline=False)
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException as e:
        print(f":: [WARN] Couldn't notify staff in {guild.id}: {e}")

def _mod_stage_state(key, rule):
    state = _mod_progress.get(key)
    if state and (time.time() - state["at"] > MOD_RETENTION or state["stage"] >= len(rule.stages)):
        _mod_progress.pop(key, None)
        state = None
    return state or {"stage": 0, "at": 0, "chain": [], "deleted": set()}

async def _mod_process(member, event, config):
    rules = _mod_active(member.guild.id, config)
    if not rules or not moderation_enabled(member.guild) or not _mod_actionable(member):
        return
    gid, uid = member.guild.id, member.id
    events = _mod_record(gid, uid, event)
    for rule in rules:
        if rule.username and not rule.username.search(member.name):
            continue
        key = (gid, uid, rule.id)
        state = _mod_stage_state(key, rule)
        index = state["stage"]
        stage = rule.stages[index]
        matched = _mod_match(rule, stage, events, state["chain"])
        if not matched:
            continue
        for e in events:
            e.consumed.add(rule.id)
        chain = state["chain"] + matched
        if index + 1 < len(rule.stages):
            _mod_progress[key] = {"stage": index + 1, "at": time.time(), "chain": chain, "deleted": state["deleted"]}
        else:
            _mod_progress.pop(key, None)
        results, removed = await _mod_execute(member, rule, stage.actions, chain, state["deleted"], config)
        if results:
            _mod_spawn(_mod_notify(member, rule, chain, results, config))
        if removed:
            for k in [k for k in _mod_progress if k[:2] == (gid, uid)]:
                del _mod_progress[k]
            break

async def moderation_on_message(message, config):
    if moderation_enabled:
        member = message.author
        if not message.guild or not isinstance(member, discord.Member) or member.bot:
            return
        try:
            await _mod_process(member, _mod_message_event(message), config)
        except Exception as e:
            print(f":: [ERROR] Moderation failed: {e}")

async def moderation_on_join(member):
    if moderation_enabled:
        if member.bot:
            return
        joined = member.joined_at.timestamp() if member.joined_at else time.time()
        try:
            await _mod_process(member, ModEvent("join", joined, created=member.created_at.timestamp()), load_config(member.guild.id))
        except Exception as e:
            print(f":: [ERROR] Moderation failed: {e}")

def _mod_chunks(text, size=1800):
    chunks, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > size:
            chunks.append(cur)
            cur = ""
        cur += ("\n" if cur else "") + line
    return chunks + [cur] if cur else chunks

def _mod_find_user(guild, query):
    query = query.strip().lstrip("@")
    if m := re.fullmatch(r"<@!?(\d+)>|(\d{15,25})", query):
        user_id = int(m.group(1) or m.group(2))
        member = guild.get_member(user_id)
        return user_id, (member.mention if member else f"`{user_id}`")
    q = query.lower()
    for attr in ("name", "global_name", "display_name"):
        for member in guild.members:
            if (getattr(member, attr, None) or "").lower() == q:
                return member.id, member.mention
    return None, None
