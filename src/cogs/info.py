from discord.ext import commands
from core.client import Rob

class InfoCog(commands.Cog):
    def __init__(self, bot: Rob):
        super().__init__()
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        description="Sends a link to Rob's official website."
    )
    async def help(self, ctx: commands.Context):
        return await ctx.send("go to https://dogo6647.github.io/rob for help :)")

    @commands.hybrid_command(
        name="about",
        description="Shows bot credits and interaction stats."
    )
    async def about(self, ctx: commands.Context):
        self.bot.reset_stats()

        ranked = []
        users = sum(g.member_count for g in self.bot.guilds)

        await ctx.send(f"haiiiii im rob, a conversational bot created by `dogo6647` :)")
        await ctx.send(f"im currently in {len(self.bot.guilds)} servers and have met {users} users, isnt that cool? :D")

        this_guild_msgs = self.bot.guild_daily_stats[ctx.guild.id]
        for guild in self.bot.guilds:
            if "COMMUNITY" not in guild.features:
                continue
            if guild.member_count <= 50:
                continue
            msg_count = self.bot.guild_daily_stats[guild.id]
            ranked.append((guild.name, guild.member_count, msg_count))

        ranked.sort(key=lambda x: x[2], reverse=True)
        top_10 = ranked[:10]

        if top_10:
            top_servers = "\n".join(f"{i+1}. {name} ({members} members) - {msgs} interactions today" for i, (name, members, msgs) in enumerate(top_10))
            await ctx.send(f"i've sent {this_guild_msgs} messages in this server today, heres today's biggest rob addicts:\n```{top_servers}```")

async def setup(bot: Rob):
    return await bot.add_cog(InfoCog(bot))