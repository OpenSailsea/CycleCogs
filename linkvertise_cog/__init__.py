from .cog import LinkvertiseCog

async def setup(bot):
    await bot.add_cog(LinkvertiseCog(bot))
