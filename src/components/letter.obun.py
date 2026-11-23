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

    @discord.ui.button(label="dm me a copy", style=discord.ButtonStyle.secondary)
    async def dm_copy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.user.send(self.letter_text)
        await interaction.response.send_message("dm sent! :D", ephemeral=True)
