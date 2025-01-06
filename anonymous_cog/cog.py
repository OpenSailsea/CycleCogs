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
        
    @_anonymous.group(name="channel")
    async def _channel(self, ctx: commands.Context):
        """Channel management commands."""
        pass
        
    @_channel.command(name="add")
    async def channel_add(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        mode: str = AnonymityMode.BASIC_ANONYMITY.value
    ):
        """
        Add a channel to anonymous messaging with specified mode.
        
        Modes:
        - no_anonymity: Uses real username and avatar
        - basic_anonymity: Uses anonymous_{user_id}_{random} format
        - full_anonymity: Uses just 'anonymous'
        
        Example: [p]anonymous channel add #channel basic_anonymity
        """
        try:
            results = await self.utils.update_channels(ctx.guild, [channel], mode, True)
            
            if results["success"]:
                await ctx.send(f"Successfully enabled anonymous messaging in {channel.mention} with mode: {mode}")
            else:
                await ctx.send(f"Failed to enable anonymous messaging in {channel.mention}")
                
        except ValueError as e:
            await ctx.send(str(e))
            
    @_channel.command(name="remove")
    async def channel_remove(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel
    ):
        """
        Remove a channel from anonymous messaging.
        
        Example: [p]anonymous channel remove #channel
        """
        results = await self.utils.update_channels(
            ctx.guild,
            [channel],
            AnonymityMode.BASIC_ANONYMITY.value,
            False
        )
        
        if results["success"]:
            await ctx.send(f"Successfully disabled anonymous messaging in {channel.mention}")
        else:
            await ctx.send(f"Failed to disable anonymous messaging in {channel.mention}")
            
    @_channel.command(name="set")
    async def channel_set(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        mode: str
    ):
        """
        Change the anonymity mode for an enabled channel.
        
        Modes:
        - no_anonymity: Uses real username and avatar
        - basic_anonymity: Uses anonymous_{user_id}_{random} format
        - full_anonymity: Uses just 'anonymous'
        
        Example: [p]anonymous channel set #channel basic_anonymity
        """
        guild_data = await self.config.guild(ctx.guild).all()
        if channel.id not in guild_data["enabled_channels"]:
            await ctx.send(f"{channel.mention} is not enabled for anonymous messaging. Use `channel add` first.")
            return
            
        try:
            results = await self.utils.update_channels(ctx.guild, [channel], mode, True)
            if results["success"]:
                await ctx.send(f"Successfully updated anonymity mode for {channel.mention} to: {mode}")
            else:
                await ctx.send(f"Failed to update anonymity mode for {channel.mention}")
        except ValueError as e:
            await ctx.send(str(e))
            
    @_channel.command(name="list")
    async def channel_list(self, ctx: commands.Context):
        """
        List all channels with anonymous messaging enabled and their modes.
        
        Example: [p]anonymous channel list
        """
        guild_data = await self.config.guild(ctx.guild).all()
        enabled_channels = guild_data["enabled_channels"]
        channel_modes = guild_data["channel_modes"]
        
        if not enabled_channels:
            await ctx.send("No channels have anonymous messaging enabled.")
            return
            
        # Build response
        response = ["**Channels with Anonymous Messaging:**"]
        for channel_id in enabled_channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                mode = channel_modes.get(str(channel_id), AnonymityMode.BASIC_ANONYMITY.value)
                response.append(f"• {channel.mention}: {mode}")
                
        await ctx.send("\n".join(response))
        
    @_anonymous.group(name="role")
    async def _role(self, ctx: commands.Context):
        """Role management commands."""
        pass
        
    @_role.command(name="add")
    async def role_add(
        self,
        ctx: commands.Context,
        role: discord.Role,
        mode: str
    ):
        """
        Add a role with specified anonymity mode.
        
        This will override channel-specific settings for users with this role.
        
        Example: [p]anonymous role add @role basic_anonymity
        """
        try:
            results = await self.utils.update_roles(ctx.guild, [role], mode)
            
            if results["success"]:
                await ctx.send(f"Successfully set anonymity mode for role {role.name} to: {mode}")
            else:
                await ctx.send(f"Failed to set anonymity mode for role {role.name}")
                
        except ValueError as e:
            await ctx.send(str(e))
            
    @_role.command(name="remove")
    async def role_remove(
        self,
        ctx: commands.Context,
        role: discord.Role
    ):
        """
        Remove a role's anonymity mode settings.
        
        Example: [p]anonymous role remove @role
        """
        async with self.config.guild(ctx.guild).role_modes() as role_modes:
            if str(role.id) in role_modes:
                del role_modes[str(role.id)]
                await ctx.send(f"Successfully removed anonymity mode for role {role.name}")
            else:
                await ctx.send(f"Role {role.name} has no anonymity mode set")
                
    @_role.command(name="set")
    async def role_set(
        self,
        ctx: commands.Context,
        role: discord.Role,
        mode: str
    ):
        """
        Change the anonymity mode for a role.
        
        Example: [p]anonymous role set @role basic_anonymity
        """
        role_modes = await self.config.guild(ctx.guild).role_modes()
        if str(role.id) not in role_modes:
            await ctx.send(f"Role {role.name} has no anonymity mode set. Use `role add` first.")
            return
            
        try:
            results = await self.utils.update_roles(ctx.guild, [role], mode)
            if results["success"]:
                await ctx.send(f"Successfully updated anonymity mode for role {role.name} to: {mode}")
            else:
                await ctx.send(f"Failed to update anonymity mode for role {role.name}")
        except ValueError as e:
            await ctx.send(str(e))
            
    @_role.command(name="list")
    async def role_list(self, ctx: commands.Context):
        """
        List all roles with their anonymity modes.
        
        Example: [p]anonymous role list
        """
        role_modes = await self.config.guild(ctx.guild).role_modes()
        
        if not role_modes:
            await ctx.send("No roles have anonymity modes set.")
            return
            
        # Build response
        response = ["**Roles with Anonymity Modes:**"]
        for role_id, mode in role_modes.items():
            role = ctx.guild.get_role(int(role_id))
            if role:
                response.append(f"• {role.name}: {mode}")
                
        await ctx.send("\n".join(response))
            
    @_anonymous.group(name="settings")
    async def _settings(self, ctx: commands.Context):
        """Configure anonymous messaging settings."""
        pass
        
    @_settings.command(name="nameformat")
    async def settings_nameformat(
        self,
        ctx: commands.Context,
        name_format: str
    ):
        """
        Set the format for basic anonymity mode usernames.
        
        Required placeholder:
        {user_id} - The user's unique anonymous ID (4 digits)
        
        Optional placeholder:
        {random} - A random number (3 digits)
        
        Default: anonymous_{user_id}_{random}
        
        Examples:
        [p]anonymous settings nameformat anon_{user_id}_{random}
        [p]anonymous settings nameformat user_{user_id}
        [p]anonymous settings nameformat anonymous_{user_id}
        """
        if "{user_id}" not in name_format:
            await ctx.send("Format must include the {user_id} placeholder.")
            return
            
        await self.config.anonymous_name_format.set(name_format)
        await ctx.send(f"Anonymous name format updated to: {name_format}")
        
    @_settings.command(name="avatar")
    async def settings_avatar(
        self,
        ctx: commands.Context,
        url: str = None
    ):
        """
        Set the default avatar URL for anonymous messages.
        
        Leave URL empty to reset to Discord's default avatar.
        
        Example: [p]anonymous settings avatar https://example.com/avatar.png
        """
        await self.config.webhook_avatar_url.set(url or "")
        if url:
            await ctx.send(f"Anonymous avatar updated to: {url}")
        else:
            await ctx.send("Anonymous avatar reset to default")
            
    @_settings.command(name="show")
    async def settings_show(self, ctx: commands.Context):
        """
        Show current anonymous messaging settings.
        
        Example: [p]anonymous settings show
        """
        global_settings = await self.config.all()
        
        response = [
            "**Anonymous Messaging Settings:**",
            f"• Name Format: {global_settings['anonymous_name_format']}",
            f"• Avatar URL: {global_settings['webhook_avatar_url'] or 'Default Discord Avatar'}"
        ]
        
        await ctx.send("\n".join(response))
            
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

        # Delete original message
        await message.delete()
            
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
