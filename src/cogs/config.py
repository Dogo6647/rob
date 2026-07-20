import re
from discord import app_commands
from discord.ext import commands
from core.client import Rob
from util.config import has_rob_admin, save_config
from typing import Optional

@commands.check(has_rob_admin)
@commands.guild_only()
class ConfigCog(commands.Cog):
    def __init__(self, bot: Rob):
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(
        name="option",
        description="Change Rob's settings to your liking."
    )
    @app_commands.describe(
        option="ID of the option to change.",
        value="Value to assign, leave empty to view the current value."
    )
    async def option(self, ctx: commands.Context, option: str, value: Optional[str]):
        assert ctx.guild
        if not value:
            return await ctx.send(f"its `{self.bot.config[option]}`")
        elif not option:
            return await ctx.send("#!option <optionId> <value>\nthats how you do it btw ;3", ephemeral=True)
    
        if option in self.bot.config:
            if not option == "model" and not option == "mailChannel" and not option == "mailTrusted":
                if value.lower() in ["enable", "disable"]:
                    self.bot.config[option] = value.lower() == "enable"
                else:
                    try:
                        self.bot.config[option] = int(value)
                    except ValueError:
                        await ctx.send("no not like that :X\nuse `enable`, `disable`, or a number", ephemeral=True)
                        return
            elif option == "mailChannel":
                match = re.match(r"<#(\d+)>", value)

                if match:
                    self.bot.config[option] = int(match.group(1))
                elif value.isdigit():
                    self.bot.config[option] = int(value)
                else:
                    await ctx.send("give me a channel mention or channel id", ephemeral=True)
                    return
            elif option == "mailTrusted" or option == "model":
                await ctx.send("you cannot change that part of my config with #!option :X", ephemeral=True)
                return
            else:
                config[option] = value
            save_config(ctx.guild.id, self.bot.config)
            await ctx.send(f"alr, `{option}` is now `{value}` :)")
        else:
            await ctx.send(f"umm idk what a `{option}` is :/", ephemeral=True)
        return
    
    @commands.hybrid_command(
        name="trust",
        description="Trusts another server's address, allowing them to send you letters."
    )
    @app_commands.describe(address="Mail address of the server to trust.")
    async def trust(self, ctx: commands.Context, address: str):
        if not address:
            await ctx.send("its like #!trust <address>", ephemeral=True)
            return

        if address not in self.bot.config["mailTrusted"]:
            self.bot.config["mailTrusted"].append(address)
            save_config(ctx.guild.id, self.bot.config)

        return await ctx.send(f"trusted `{address}` :)")
    
    @commands.hybrid_command(
        name="untrust",
        description="Stops trusting another server's address, blocking them from sending you letters."
    )
    @app_commands.describe(address="Mail address of the server to untrust.")
    async def untrust(self, ctx: commands.Context, address: str):
        if not address:
            await ctx.send("its like #!untrust <address>", ephemeral=True)
            return

        if address in self.bot.config["mailTrusted"]:
            self.bot.config["mailTrusted"].remove(address)
            save_config(ctx.guild.id, self.bot.config)

        return await ctx.send(f"bleh, untrusted `{address}` -_-")

async def setup(bot: Rob):
    return await bot.add_cog(ConfigCog(bot))