"""
Anonymous cog module for Red-DiscordBot.
Provides customizable anonymous messaging functionality.
"""
from .cog import Anonymous

async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Anonymous(bot))
