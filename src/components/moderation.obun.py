class ModerationToggle(discord.ui.Button):
    def __init__(self, rule_name, number, enabled):
        super().__init__(
            label=str(number),
            style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.secondary,
            row=0
        )
        self.rule_name = rule_name

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view is None:
            await interaction.response.send_message("This moderation menu is no longer available.", ephemeral=True)
            return

        config = load_config(view.guild.id)
        enabled = config.get("moderationRules", [])

        if self.rule_name in enabled:
            enabled.remove(self.rule_name)
        else:
            enabled.append(self.rule_name)

        config["moderationRules"] = enabled
        save_config(view.guild.id, config)
        view.update_buttons()

        await interaction.response.edit_message(embed=view.make_embed(), view=view)


class ModerationView(discord.ui.View):
    def __init__(self, guild, author_id):
        super().__init__(timeout=180)

        self.guild = guild
        self.author_id = author_id
        self.rules = moderation_rules_for(guild.id)
        self.names = sorted(n for n, f in self.rules.items() if not f.custom) + sorted(n for n, f in self.rules.items() if f.custom)
        self.page = 0
        self.per_page = 5

        self.update_buttons()

    @property
    def max_page(self):
        return max(0, (len(self.names) - 1) // self.per_page)

    def enabled(self):
        return set(load_config(self.guild.id).get("moderationRules", []))

    def update_buttons(self):
        for item in [i for i in self.children if isinstance(i, ModerationToggle)]:
            self.remove_item(item)

        enabled = self.enabled()
        start = self.page * self.per_page
        for i, name in enumerate(self.names[start:start + self.per_page], start=start + 1):
            self.add_item(ModerationToggle(name, i, name in enabled))

        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.max_page

    def make_embed(self):
        enabled = self.enabled()
        start = self.page * self.per_page

        lines = []
        for i, name in enumerate(self.names[start:start + self.per_page], start=start + 1):
            mark = "🟢" if name in enabled else "⚫"
            tag = " (custom)" if self.rules[name].custom else ""
            lines.append(f"**{i}. {mark} {name}**{tag}\n{self.rules[name].description}")

        missing = _mod_missing(self.guild)
        if missing:
            status = "⛔ moderation is **inactive**, i need a role with " + ", ".join(f"`{p.replace('_', ' ')}`" for p in missing)
        else:
            status = "moderation is **active**"

        embed = discord.Embed(
            title="🛡️ moderation [BETA]",
            description=status + "\n\n" + "\n\n".join(lines),
            color=0x55ACEE
        )
        embed.set_footer(
            text=f"{self.page + 1}/{self.max_page + 1} | {len(enabled & set(self.names))}/{len(self.names)} rules enabled | press a number to toggle"
        )
        return embed

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction, button):
        self.page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="→", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction, button):
        self.page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)
