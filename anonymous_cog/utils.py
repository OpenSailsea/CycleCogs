"""
Utility functions for the Anonymous cog.
"""
from enum import Enum
import random
import string
import discord
from redbot.core import Config
from typing import Dict, List, Optional, Union

class AnonymityMode(Enum):
    """Enumeration of available anonymity modes."""
    NO_ANONYMITY = "no_anonymity"  # Uses real username and avatar
    BASIC_ANONYMITY = "basic_anonymity"  # Uses anonymous_{user_id}_{random} format
    FULL_ANONYMITY = "full_anonymity"  # Uses just 'anonymous'

class AnonymousUtils:
    """Utility class for anonymous messaging functionality."""
    
    def __init__(self, config: Config):
        self.config = config
        
    async def generate_anonymous_id(self, user_id: int, guild_id: int) -> str:
        """Generate or retrieve a consistent anonymous ID for a user."""
        async with self.config.guild_from_id(guild_id).user_ids() as user_ids:
            if str(user_id) not in user_ids:
                while True:
                    new_id = ''.join(random.choices(string.digits, k=4))
                    if new_id not in user_ids.values():
                        user_ids[str(user_id)] = new_id
                        break
            return user_ids[str(user_id)]
            
    async def get_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        """Create and return a webhook for the specified channel."""
        try:
            webhook = await channel.create_webhook(name="Anonymous Message")
            return webhook
        except discord.HTTPException as e:
            raise discord.HTTPException(f"Failed to create webhook: {str(e)}")
            
    async def get_anonymity_mode(
        self, 
        guild: discord.Guild, 
        channel: discord.TextChannel, 
        member: discord.Member
    ) -> AnonymityMode:
        """Determine the appropriate anonymity mode for a user in a channel."""
        # Check role-based modes first
        role_modes = await self.config.guild(guild).role_modes()
        for role in member.roles:
            if str(role.id) in role_modes:
                return AnonymityMode(role_modes[str(role.id)])
                
        # Fall back to channel mode
        channel_modes = await self.config.guild(guild).channel_modes()
        return AnonymityMode(channel_modes.get(
            str(channel.id),
            AnonymityMode.BASIC_ANONYMITY.value
        ))
        
    async def format_webhook_name(
        self, 
        mode: AnonymityMode, 
        user: discord.Member,
        guild: discord.Guild
    ) -> str:
        """Format the webhook name based on anonymity mode."""
        if mode == AnonymityMode.NO_ANONYMITY:
            return user.display_name
        elif mode == AnonymityMode.BASIC_ANONYMITY:
            user_id = await self.generate_anonymous_id(user.id, guild.id)
            name_format = await self.config.anonymous_name_format()
            
            # 准备格式化参数
            format_params = {"user_id": user_id}
            
            # 如果格式中包含 random 占位符，则生成随机数
            if "{random}" in name_format:
                format_params["random"] = ''.join(random.choices(string.digits, k=3))
                
            try:
                return name_format.format(**format_params)
            except KeyError:
                # 如果格式化失败，返回默认格式
                return f"anonymous_{user_id}"
        else:  # FULL_ANONYMITY
            return "anonymous"
            
    async def update_channels(
        self,
        guild: discord.Guild,
        channels: List[discord.TextChannel],
        mode: str,
        enable: bool = True
    ) -> Dict[str, List[str]]:
        """
        Update multiple channels' anonymous settings.
        
        Returns:
            Dict with 'success' and 'failed' lists of channel names
        """
        try:
            mode_enum = AnonymityMode(mode)
        except ValueError:
            raise ValueError(f"Invalid mode. Available modes: {', '.join(m.value for m in AnonymityMode)}")
            
        results = {"success": [], "failed": []}
        
        async with self.config.guild(guild).all() as guild_data:
            for channel in channels:
                try:
                    if enable:
                        if channel.id not in guild_data["enabled_channels"]:
                            guild_data["enabled_channels"].append(channel.id)
                        guild_data["channel_modes"][str(channel.id)] = mode_enum.value
                    else:
                        if channel.id in guild_data["enabled_channels"]:
                            guild_data["enabled_channels"].remove(channel.id)
                            guild_data["channel_modes"].pop(str(channel.id), None)
                    results["success"].append(channel.name)
                except Exception:
                    results["failed"].append(channel.name)
                    
        return results
        
    async def update_roles(
        self,
        guild: discord.Guild,
        roles: List[discord.Role],
        mode: str
    ) -> Dict[str, List[str]]:
        """
        Update multiple roles' anonymous settings.
        
        Returns:
            Dict with 'success' and 'failed' lists of role names
        """
        try:
            mode_enum = AnonymityMode(mode)
        except ValueError:
            raise ValueError(f"Invalid mode. Available modes: {', '.join(m.value for m in AnonymityMode)}")
            
        results = {"success": [], "failed": []}
        
        async with self.config.guild(guild).role_modes() as role_modes:
            for role in roles:
                try:
                    role_modes[str(role.id)] = mode_enum.value
                    results["success"].append(role.name)
                except Exception:
                    results["failed"].append(role.name)
                    
        return results
        
    async def send_anonymous_message(
        self,
        message: discord.Message,
        webhook: discord.Webhook,
        mode: AnonymityMode
    ) -> None:
        """Send a message through the webhook with appropriate anonymity settings."""
        try:
            # Format webhook name
            webhook_name = await self.format_webhook_name(
                mode,
                message.author,
                message.guild
            )
            
            # Get avatar URL based on mode
            avatar_url = None
            if mode == AnonymityMode.NO_ANONYMITY:
                avatar_url = message.author.display_avatar.url
            else:
                avatar_url = await self.config.webhook_avatar_url()
                
            # Send message through webhook
            await webhook.send(
                content=message.content,
                username=webhook_name,
                avatar_url=avatar_url,
                files=[await a.to_file() for a in message.attachments]
            )
            
            # Delete original message
            await message.delete()
            
        except Exception as e:
            await message.channel.send(
                f"Error sending anonymous message: {str(e)}",
                delete_after=5
            )
