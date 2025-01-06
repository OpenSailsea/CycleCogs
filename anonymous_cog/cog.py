"""
Anonymous messaging system cog for Red-DiscordBot.
Provides customizable anonymous messaging functionality with multiple anonymity modes.
"""
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box, pagify
from typing import Dict, Optional, List
from .utils import AnonymityMode, AnonymousUtils

class Anonymous(commands.Cog):
    """
    A customizable anonymous messaging system.
    
    Features:
    - Multiple anonymity modes
    - Per-channel configuration
    - Role-based default modes
    - Admin tracking capabilities
    """
    
    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8927348923,  # Unique identifier for config
            force_registration=True
        )
        
        # Default global settings
        default_global = {
            "anonymous_name_format": "anonymous_{user_id}_{random}",  # Format for basic anonymity mode
            "webhook_avatar_url": "",  # Default webhook avatar URL
        }
        
        # Default guild settings
        default_guild = {
            "enabled_channels": [],  # List of channel IDs where anonymous messaging is enabled
            "channel_modes": {},  # Channel ID to anonymity mode mapping
            "role_modes": {},  # Role ID to anonymity mode mapping
            "user_ids": {},  # Mapping of anonymous IDs to real user IDs (for basic anonymity mode)
            "active_webhooks": {}  # Temporary storage for active webhooks
        }
        
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)
        
        # Initialize utils
        self.utils = AnonymousUtils(self.config)
            
    @commands.group(name="anonymous")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def _anonymous(self, ctx: commands.Context):
        """Anonymous messaging system configuration commands."""
        pass
        
    @_anonymous.command(name="enablechannels")
    async def enable_channels(
        self, 
        ctx: commands.Context, 
        channels: commands.Greedy[discord.TextChannel],
        mode: str = AnonymityMode.BASIC_ANONYMITY.value
    ):
        """
        Enable anonymous messaging in multiple channels with specified mode.
        
        Modes:
        - no_anonymity: Uses real username and avatar
        - basic_anonymity: Uses anonymous_{user_id}_{random} format
        - full_anonymity: Uses just 'anonymous'
        
        Example: [p]anonymous enablechannels #channel1 #channel2 #channel3 basic_anonymity
        """
        if not channels:
            await ctx.send("Please specify at least one channel.")
            return
            
        try:
            results = await self.utils.update_channels(ctx.guild, channels, mode, True)
            
            # Format response
            response = []
            if results["success"]:
                response.append(f"Successfully enabled anonymous messaging in: {', '.join(results['success'])}")
            if results["failed"]:
                response.append(f"Failed to enable in: {', '.join(results['failed'])}")
                
            await ctx.send("\n".join(response))
            
        except ValueError as e:
            await ctx.send(str(e))
        
    @_anonymous.command(name="disablechannels")
    async def disable_channels(
        self,
        ctx: commands.Context,
        channels: commands.Greedy[discord.TextChannel]
    ):
        """
        Disable anonymous messaging in multiple channels.
        
        Example: [p]anonymous disablechannels #channel1 #channel2 #channel3
        """
        if not channels:
            await ctx.send("Please specify at least one channel.")
            return
            
        results = await self.utils.update_channels(ctx.guild, channels, AnonymityMode.BASIC_ANONYMITY.value, False)
        
        # Format response
        response = []
        if results["success"]:
            response.append(f"Successfully disabled anonymous messaging in: {', '.join(results['success'])}")
        if results["failed"]:
            response.append(f"Failed to disable in: {', '.join(results['failed'])}")
            
        await ctx.send("\n".join(response))
        
    @_anonymous.command(name="setrolemodes")
    async def set_role_modes(
        self, 
        ctx: commands.Context, 
        mode: str,
        roles: commands.Greedy[discord.Role]
    ):
        """
        Set the default anonymity mode for multiple roles.
        
        This will override channel-specific settings.
        
        Example: [p]anonymous setrolemodes basic_anonymity @role1 @role2 @role3
        """
        if not roles:
            await ctx.send("Please specify at least one role.")
            return
            
        try:
            results = await self.utils.update_roles(ctx.guild, roles, mode)
            
            # Format response
            response = []
            if results["success"]:
                response.append(f"Successfully set anonymity mode for roles: {', '.join(results['success'])}")
            if results["failed"]:
                response.append(f"Failed to set mode for roles: {', '.join(results['failed'])}")
                
            await ctx.send("\n".join(response))
            
        except ValueError as e:
            await ctx.send(str(e))
            
    @_anonymous.command(name="lookup")
    async def lookup_user(self, ctx: commands.Context, anonymous_id: str):
        """Look up the real user behind a basic anonymity mode ID."""
        async with self.config.guild(ctx.guild).user_ids() as user_ids:
            for user_id, anon_id in user_ids.items():
                if anon_id == anonymous_id:
                    try:
                        user = await ctx.guild.fetch_member(int(user_id))
                        await ctx.send(
                            f"Anonymous ID {anonymous_id} belongs to: {user.mention}",
                            allowed_mentions=discord.AllowedMentions.none()
                        )
                        return
                    except discord.NotFound:
                        await ctx.send("User not found in server.")
                        return
                        
        await ctx.send("Anonymous ID not found.")
        
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle messages in anonymous channels."""
        if not message.guild or message.author.bot:
            return
            
        # Check if channel is enabled for anonymous messages
        guild_data = await self.config.guild(message.guild).all()
        if message.channel.id not in guild_data["enabled_channels"]:
            return
            
        # Get anonymity mode
        mode = await self.utils.get_anonymity_mode(
            message.guild,
            message.channel,
            message.author
        )
        
        # Create webhook
        webhook = await self.utils.get_webhook(message.channel)
        
        try:
            # Send anonymous message
            await self.utils.send_anonymous_message(message, webhook, mode)
        except Exception as e:
            await message.channel.send(
                f"Error sending anonymous message: {str(e)}",
                delete_after=5
            )
        finally:
            # Clean up webhook
            await webhook.delete()
