import discord

class LetterView(discord.ui.View):
    def __init__(self, letter_text):
        super().__init__(timeout=None)
        self.letter_text = letter_text

    @discord.ui.button(label="open letter!", style=discord.ButtonStyle.primary)
    async def open_letter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            self.letter_text,
            ephemeral=True
        )

class PhonebookView(discord.ui.View):
    def __init__(self, entries, author_id):
        super().__init__(timeout=180)

        self.entries = entries
        self.author_id = author_id
        self.page = 0
        self.per_page = 5

        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.max_page

    @property
    def max_page(self):
        return max(0, (len(self.entries) - 1) // self.per_page)

    def make_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page

        lines = []

        for i, (guild_name, address) in enumerate(
            self.entries[start:end],
            start=start + 1
        ):
            lines.append(
                f"**{i}. {guild_name}**\n"
                f"`{address}`"
            )

        embed = discord.Embed(
            title="☎️ phonebook",
            description="\n\n".join(lines) or "*empty*",
            color=0x87CEEB
        )

        embed.set_footer(
            text=f"{self.page + 1}/{self.max_page + 1} | {len(self.entries)} trusted addresses | use #!send <addr> <msg>"
        )

        return embed

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id

    @discord.ui.button(label="←", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction, button):
        self.page -= 1
        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self
        )

    @discord.ui.button(label="→", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction, button):
        self.page += 1
        self.update_buttons()

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self
        )
