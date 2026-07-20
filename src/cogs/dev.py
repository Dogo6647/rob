import io
from discord.ext import commands
from core.client import Rob
from contextlib import redirect_stdout

@commands.is_owner()
class DevCog(commands.Cog):
    def __init__(self, bot: Rob):
        super().__init__()
        self.bot = bot

    @commands.command(name="eval", description="Evaluates Python code.")
    async def eval(self, ctx: commands.Context, *, code: str):
        print(f":: [SECURITY WARNING] - executing eval '{code}'.")
        buffer = io.StringIO()

        try:
            with redirect_stdout(buffer):
                exec(code)

            output = buffer.getvalue() or "(no output)"
            await ctx.channel.send(f"```\n{output}\n```")
        except Exception as e:
            await ctx.channel.send(f"```\n{type(e).__name__}: {e}\n```")
        return

    @commands.command(name="reload", description="Reloads a loaded cog.")
    async def reload(self, ctx: commands.Context, cog: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog}")
            return await ctx.reply(f":: Cog {cog} loaded successfully")
        except Exception as e:
            return await ctx.reply(f":: Cog {cog} failed to load: {e}")

async def setup(bot: Rob):
    return await bot.add_cog(DevCog(bot))