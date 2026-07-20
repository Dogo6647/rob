import re
from discord import app_commands, Embed, Guild
from discord.ext import commands
from core.client import Rob
from components.mail import LetterView, PhonebookView
from util.config import load_config, get_mail_channel

class MailCog(commands.Cog):
    def __init__(self, bot: Rob):
        super().__init__()
        self.bot = bot

    def guild_address(self, guild: Guild):
        slug = re.sub(r"[^a-z0-9]+", "-", guild.name.lower())
        slug = slug.strip("-")
        return f"{slug}-{str(guild.id)[-2:]}"

    @commands.hybrid_command(
        name="address",
        description="Shows your server's robmail address."
    )
    async def address(self, ctx: commands.Context):
        return await ctx.send(f"this server's address is `{self.guild_address(ctx.guild)}`")
    
    @commands.hybrid_command(
        name="phonebook",
        description="Presents all addresses trusted by the current server."
    )
    async def phonebook(self, ctx: commands.Context):
        trusted = self.bot.config.get("mailTrusted", [])

        if not trusted:
            return await ctx.send(
                "this server's phonebook is empty :(\nuse `#!trust <address>` to add servers"
            )

        entries = []

        for address in trusted:
            guild_name = "unknown server"
            for guild in self.bot.guilds:
                if self.guild_address(guild) == address:
                    guild_name = guild.name
                    break

            entries.append((guild_name, address))

        view = PhonebookView(entries, ctx.author.id)
        return await ctx.send(embed=view.make_embed(), view=view)
    
    @commands.hybrid_command(
        name="send",
        description="Sends a letter to a specified robmail address."
    )
    @app_commands.describe(
        address="Address of the server to send the letter to.",
        message="Content of this letter."
    )
    async def send(self, ctx: commands.Context, address: str, *, message: str):
        if not address or not message:
            return await ctx.send("its like #!send <address> <message>", ephemeral=True)

        sender_address = self.guild_address(ctx.guild)
        target_guild = None

        for guild in self.bot.guilds:
            if self.guild_address(guild) == address:
                target_guild = guild
                break

        if target_guild is None:
            await ctx.send("i couldn't find that server :(", ephemeral=True)
            return

        sender_cfg = load_config(ctx.guild.id)
        receiver_cfg = load_config(target_guild.id)

        if address not in sender_cfg["mailTrusted"]:
            return await ctx.send(f"that address isn't on your trusted list, run '#!trust {address}'", ephemeral=True)

        if sender_address not in receiver_cfg["mailTrusted"]:
            return await ctx.send(f"that server hasn't trusted you yet, ask them to run '#!trust {sender_address}'", ephemeral=True)

        channel = get_mail_channel(target_guild, receiver_cfg)

        if not channel:
            return await ctx.send("that server has nowhere i can deliver mail :(", ephemeral=True)

        if not channel:
            return await ctx.send("delivery failed :(", ephemeral=True)

        letter_text = (
            f"Dear {target_guild.name}:\n\n"
            f"{message}\n\n"
            f"- {message.author.name}"
        )

        embed = Embed(
            title="📬 you've got mail!",
            description=f"a letter has arrived from **{message.guild.name}**.",
            color=0xF4D58D
        )

        await channel.send(
            embed=embed,
            view=LetterView(letter_text)
        )
        return await ctx.send("letter delivered! :D", ephemeral=True)

async def setup(bot: Rob):
    return await bot.add_cog(MailCog(bot))