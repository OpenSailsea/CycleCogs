from .cog import VerifyCog

async def setup(bot):
    await bot.add_cog(VerifyCog(bot))
