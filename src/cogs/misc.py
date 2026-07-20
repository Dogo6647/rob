from aiohttp import ClientSession
from discord import app_commands
from discord.ext import commands
from core.client import Rob
from util.gen import generate_response
from util.sys import websearch

class MiscCog(commands.Cog):
    def __init__(self, bot: Rob):
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(
        name="dadjoke",
        description="Sends a random joke from the icanhazadadjoke API."
    )
    async def dadjoke(self, ctx: commands.Context):
        async with ClientSession(headers={
            "Accept": "text/plain",
            "User-Agent": "Rob/1.0.0 (Discord Bot; https://dogo6647.github.io/rob)"
        }) as session:
            async with session.get("https://icanhazdadjoke.com/") as response:
                joke = await response.text()
                return await ctx.send(joke)
            
    @commands.hybrid_command(
        name="owobonk",
        description="Hits Rob with the magic owo stick that temporarily uwuifies his responses.",
        guild_only=True
    )
    async def owobonk(self, ctx: commands.Context):
        self.bot.history.append({
            "role": "system",
            "content": "You have been hit with the OwO magic stik. Youw head huwts a wittwe, and you can onwwy tawwk in uwu femboy furry language fwom now on. Replace evewy 'r' you say with 'w'. Occassionawwy say stufz like *blushes*, *giggles*, rawr, and hehe~. Use '~' non-spawringwy."
        })

        response = await generate_response(
            "BANNNNNNGGGG!!!!! say your head is feeling funny. Start your response with 'ow' or similar.",
            self.bot.history,
            self.bot.config.get("model"),
            self.bot.config.get("dumb"),
            f"the {ctx.guild.name} server" if ctx.guild else "DMs"
        )
        await ctx.send(f"🪄💥 >~< {response}")

    @commands.hybrid_command(
        name="search",
        description="Searches for stuff on the web using DuckDuckGo and provides a Rob-certified™ summary.",
    )
    @app_commands.describe(query="Query to search on the web.")
    async def search(self, ctx: commands.Context, query: str):
        async def update_status(text):
            await ctx.send(text)

        result = await websearch(query, update_status)
        response = await generate_response(
            f"Summarize the following text so that it's relevant to the conversation: '{result}'. Use the amount of words necessary to make a detailed explanation.",
            self.bot.history,
            self.bot.config.get("model"),
            self.bot.config.get("dumb"),
            f"the {ctx.guild.name} server" if ctx.guild else "DMs"
        )
        await ctx.send(response)
        return

async def setup(bot: Rob):
    return await bot.add_cog(MiscCog(bot))