    if message.guild and (message.content.split(None, 1)[:1] == [f"{cmdprefix}moderation"] or message.content.split(None, 1)[:1] == [f"{cmdprefix}mod"]):
        userperms = message.author.guild_permissions
        if not userperms.administrator and not all(getattr(userperms, perm) for perm in MOD_PERMS) and str(message.author.id) != str(OWNER_ID):
            await message.channel.send("...you dont have a mod role yk\ngonna need that to change my mod settings :3")
            return

        head, _, body = message.content.partition("\n")
        args = head.split()[1:]
        sub = args[0].lower() if args else ""

        # everything except "clear" is staff channel-only
        if not sub == "clear":
            staff = get_moderation_channel(message.guild, config)
            if not staff:
                await message.channel.send("i cant find a staff channel to use :/\nset one with `" + cmdprefix + "option staffChannel <#channel>` first")
                return
            if message.channel.id != staff.id and getattr(message.channel, "parent_id", None) != staff.id:
                await message.channel.send(f"this moderation command only works in {staff.mention} :3")
                return

        moderation_rules.clear()
        moderation_rules.update(moderation_load_rules())
        guild_rules = moderation_rules_for(message.guild.id)

        if sub == "":
            if not guild_rules:
                await message.channel.send("i dont have any moderation rules installed :/")
                return
            view = ModerationView(message.guild, message.author.id)
            await message.channel.send(embed=view.make_embed(), view=view)
            return

        if sub == "rule":
            if len(args) != 2:
                await message.channel.send(f"its like `{cmdprefix}moderation rule <rulename>`")
                return
            found = moderation_find_rule(message.guild.id, args[1])
            if not found:
                await message.channel.send(f"i dont have a rule called `{args[1]}` :/")
                return
            state = "enabled" if found.name in config["moderationRules"] else "disabled"
            kind = "custom" if found.custom else "built-in"
            await message.channel.send(f"**{found.name}** ({kind}, {state}):")
            for chunk in _mod_chunks(found.source):
                await message.channel.send(f"```\n{chunk}\n```")
            return

        if sub == "newrule":
            fence = re.search(r"```(?:rmpl)?[ \t]*\n(.*?)```", body, re.DOTALL)
            if len(args) != 2 or not fence:
                await message.channel.send(f"its like\n{cmdprefix}moderation newRule <rulename>\n\\`\\`\\`\nrule contents\n\\`\\`\\`")
                return
            name, text = args[1], fence.group(1).replace("\r\n", "\n").strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
                await message.channel.send("rule names can only use letters, numbers, `_` and `-` (max 32 characters)")
                return
            if moderation_find_rule(message.guild.id, name):
                await message.channel.send(f"a rule called `{name}` already exists :/ (use `{cmdprefix}moderation deleteRule {name}` first if its a custom one)")
                return
            used = moderation_custom_size(message.guild.id)
            size = len(text.encode("utf-8"))
            if used + size > MOD_CUSTOM_LIMIT:
                await message.channel.send(f"thats too much :X\ncustom rules can only be {MOD_CUSTOM_LIMIT} bytes in total, you're using {used} and this one is {size}")
                return
            try:
                parsed = _mod_parse_file(name, text, custom=True, strict=True)
            except ValueError as e:
                await message.channel.send(f"i cant understand that rule, {e}")
                return
            custom = dict(moderation_custom(message.guild.id))
            custom[name] = parsed
            moderation_custom_save(message.guild.id, custom)
            await message.channel.send(f"added `{name}` ({used + size}/{MOD_CUSTOM_LIMIT} bytes used)\nit's off until you enable it in `{cmdprefix}moderation` :)")
            return

        if sub == "deleterule":
            if len(args) != 2:
                await message.channel.send(f"its like `{cmdprefix}moderation deleteRule <rulename>`")
                return
            found = moderation_find_rule(message.guild.id, args[1])
            if not found:
                await message.channel.send(f"i dont have a rule called `{args[1]}` :/")
                return
            if not found.custom:
                await message.channel.send(f"`{found.name}` is a built in rule, i can only delete custom ones")
                return
            custom = dict(moderation_custom(message.guild.id))
            del custom[found.name]
            moderation_custom_save(message.guild.id, custom)
            if found.name in config["moderationRules"]:
                config["moderationRules"].remove(found.name)
                save_config(message.guild.id, config)
            await message.channel.send(f"deleted `{found.name}` ({moderation_custom_size(message.guild.id)}/{MOD_CUSTOM_LIMIT} bytes used)")
            return

        if sub in ("watch", "enable", "ignore", "disable"):
            if len(args) != 2:
                await message.channel.send(f"its like `{cmdprefix}moderation {sub} <rulename>`")
                return
            found = moderation_find_rule(message.guild.id, args[1])
            if not found:
                await message.channel.send(f"i dont have a rule called `{args[1]}` :/")
                return
            active = found.name in config["moderationRules"]
            if sub == "watch" or sub == "enable":
                if active:
                    await message.channel.send(f"i'm already watching for `{found.name}` :D")
                    return
                config["moderationRules"].append(found.name)
                save_config(message.guild.id, config)
                await message.channel.send(f"rule `{found.name}` is now on :)")
            else:
                if not active:
                    await message.channel.send(f"rule `{found.name}` is already off :3")
                    return
                config["moderationRules"].remove(found.name)
                save_config(message.guild.id, config)
                await message.channel.send(f"rule `{found.name}` is now off :)")
            return

        if sub == "clear":
            if len(args) < 2:
                await message.channel.send(f"its like `{cmdprefix}moderation clear <username>`")
                return
            target_id, label = _mod_find_user(message.guild, " ".join(args[1:]))
            if target_id is None:
                await message.channel.send("i cant find anyone with that username :/\nif they left, use their user id")
                return
            count = moderation_reset(message.guild.id, target_id)
            if count:
                await message.channel.send(f"cleared {count} offense{'s' if count != 1 else ''} for {label} :)")
            else:
                await message.channel.send(f"{label} doesnt have any offenses")
            return

        await message.channel.send(
            "moderation commands:\n"
            f"- `{cmdprefix}moderation` - toggle rules\n"
            f"- `{cmdprefix}moderation rule <rulename>` - show a rule\n"
            f"- `{cmdprefix}moderation watch/enable <rulename>` - activate a rule\n"
            f"- `{cmdprefix}moderation ignore/disable <rulename>` - deactivate a rule\n"
            f"- `{cmdprefix}moderation newRule <rulename> (newline) <codeblock>` - add a custom rule\n"
            f"- `{cmdprefix}moderation deleteRule <rulename>` - delete a custom rule\n"
            f"- `{cmdprefix}moderation clear <username>` - reset someone's offenses"
        )
        return
