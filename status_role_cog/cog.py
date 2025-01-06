from typing import Dict, Optional
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box


class StatusRole(commands.Cog):
    """Automatically assign roles based on user status"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=844662891, force_registration=True)
        
        default_guild = {
            "status_roles": {}  # Format: {"status_text": role_id}
        }
        
        self.config.register_guild(**default_guild)

    @commands.group()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def statusrole(self, ctx: commands.Context):
        """Status role management commands"""
        pass

    @statusrole.command(name="add")
    async def add_status_role(self, ctx: commands.Context, role: discord.Role, *, status_text: str):
        """Add status text and corresponding role
        
        Example:
        [p]statusrole add @VIP playing APEX
        """
        async with self.config.guild(ctx.guild).status_roles() as status_roles:
            status_roles[status_text] = role.id
            
        await ctx.send(f"Added: Role {role.mention} will be granted when status contains `{status_text}`")

    @statusrole.command(name="remove")
    async def remove_status_role(self, ctx: commands.Context, *, status_text: str):
        """Remove status text and corresponding role
        
        Example:
        [p]statusrole remove playing APEX
        """
        async with self.config.guild(ctx.guild).status_roles() as status_roles:
            if status_text in status_roles:
                del status_roles[status_text]
                await ctx.send(f"Removed configuration for status text `{status_text}`")
            else:
                await ctx.send("No configuration found for this status text")

    @statusrole.command(name="list")
    async def list_status_roles(self, ctx: commands.Context):
        """List all status texts and corresponding roles"""
        status_roles = await self.config.guild(ctx.guild).status_roles()
        
        if not status_roles:
            await ctx.send("No status roles configured")
            return
            
        msg = "Status Role Configurations:\n\n"
        for status, role_id in status_roles.items():
            role = ctx.guild.get_role(role_id)
            if role:
                msg += f"• Status: {status}\n  Role: {role.name}\n"
            
        await ctx.send(box(msg))

    async def _update_member_roles(self, member: discord.Member, status: Optional[str] = None):
        """Update member's roles based on their status"""
        if not member.guild:
            return
            
        status_roles = await self.config.guild(member.guild).status_roles()
        if not status_roles:
            return
            
        # Get current status
        if status is None:
            # Check for custom status
            if member.activity and member.activity.type == discord.ActivityType.custom:
                status = member.activity.state
            else:
                status = ""
                
        # Check each configured status text
        for status_text, role_id in status_roles.items():
            role = member.guild.get_role(role_id)
            if not role:
                continue
                
            has_role = role in member.roles
                
            # Add role if status contains configured text
            if status and status_text.lower() in status.lower():
                if not has_role:
                    try:
                        await member.add_roles(role, reason="Status match")
                    except discord.Forbidden:
                        continue
            # Remove role if status doesn't contain configured text
            elif has_role:
                try:
                    await member.remove_roles(role, reason="Status no longer matches")
                except discord.Forbidden:
                    continue

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Listen for presence update events"""
        # Check if custom status changed
        before_status = before.activity.state if before.activity and before.activity.type == discord.ActivityType.custom else None
        after_status = after.activity.state if after.activity and after.activity.type == discord.ActivityType.custom else None
        
        if before_status != after_status:
            await self._update_member_roles(after, after_status)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Listen for member update events"""
        # Check if activity status changed
        if before.activity != after.activity:
            await self._update_member_roles(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Listen for member join events"""
        await self._update_member_roles(member)
