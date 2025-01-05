from typing import Optional
import discord
from redbot.core import commands, Config
from linkvertise import LinkvertiseClient
from discord import Webhook, SyncWebhook
import aiohttp
from .utils import extract_urls, convert_to_linkvertise

FOOTER_TEXT = "\n---\n*Links in this message have been converted to Linkvertise links. Support this server to whitelist your messages.*"

class LinkvertiseCog(commands.Cog):
    """Convert message links to Linkvertise links"""
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "account_id": None,
            "whitelisted_role_id": None,
            "webhook_url": None
        }
        self.config.register_guild(**default_guild)
        self.linkvertise_client = LinkvertiseClient()
        self.webhook_session = aiohttp.ClientSession()
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Process each message"""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Check if in a server
        if not isinstance(message.channel, discord.TextChannel):
            return
            
        # Get guild settings
        guild_config = self.config.guild(message.guild)
        account_id = await guild_config.account_id()
        if not account_id:
            return
            
        # Check whitelist role
        whitelisted_role_id = await guild_config.whitelisted_role_id()
        if whitelisted_role_id:
            member_roles = [role.id for role in message.author.roles]
            if whitelisted_role_id in member_roles:
                return
                
        # Extract and check links
        url_infos = extract_urls(message.content)
        if not url_infos:
            return
            
        # Convert all links
        new_content = message.content
        offset = 0
        
        for url, start, end in url_infos:
            new_url = convert_to_linkvertise(url, self.linkvertise_client, account_id)
            if new_url == url:  # Conversion failed
                continue
                
            # Update content with new link
            new_content = (
                new_content[:start + offset] +
                new_url +
                new_content[end + offset:]
            )
            # Update offset for next replacement
            offset += len(new_url) - len(url)
            
        if new_content == message.content:  # No links were converted
            return
            
        new_content += FOOTER_TEXT
        
        # Delete original message and send new one
        try:
            await message.delete()
            
            webhook_url = await guild_config.webhook_url()
            if webhook_url and self.webhook_session:
                # Send message using webhook
                async with aiohttp.ClientSession() as session:
                    webhook = Webhook.from_url(webhook_url, session=session)
                    await webhook.send(
                        content=new_content,
                        username=message.author.display_name,
                        avatar_url=message.author.display_avatar.url,
                        allowed_mentions=discord.AllowedMentions.none()
                    )
            else:
                # Send message normally
                await message.channel.send(
                    new_content,
                    allowed_mentions=discord.AllowedMentions.none()
                )
        except discord.Forbidden:
            # If no permission to delete, reply with converted links
            await message.reply(
                f"Links converted: {new_url}" + FOOTER_TEXT,
                allowed_mentions=discord.AllowedMentions.none()
            )
    
    @commands.group(name="linkvertise", invoke_without_command=True)
    @commands.admin_or_permissions(administrator=True)
    async def linkvertise_group(self, ctx: commands.Context):
        """Linkvertise settings command group"""
        await ctx.send_help(ctx.command)
    
    @linkvertise_group.command(name="setrole")
    @commands.admin_or_permissions(administrator=True)
    async def set_whitelisted_role(self, ctx: commands.Context, role: discord.Role):
        """Set whitelist role"""
        await self.config.guild(ctx.guild).whitelisted_role_id.set(role.id)
        await ctx.send(f"Set {role.name} as whitelist role")
    
    @linkvertise_group.command(name="setid")
    @commands.admin_or_permissions(administrator=True)
    async def set_account_id(self, ctx: commands.Context, account_id: int):
        """Set Linkvertise account ID"""
        await self.config.guild(ctx.guild).account_id.set(account_id)
        await ctx.send("Updated Linkvertise account ID")
            
    @linkvertise_group.command(name="setwebhook")
    @commands.admin_or_permissions(administrator=True)
    async def set_webhook(self, ctx: commands.Context, webhook_url: str):
        """Set webhook URL for sending messages"""
        # Validate webhook URL
        try:
            async with aiohttp.ClientSession() as session:
                webhook = Webhook.from_url(webhook_url, session=session)
                # Try sending test message
                await webhook.send("Webhook test message", username="Linkvertise Bot")
        except Exception as e:
            await ctx.send(f"Invalid webhook URL: {str(e)}")
            return
            
        await self.config.guild(ctx.guild).webhook_url.set(webhook_url)
        await ctx.send("Updated webhook URL")
        # Delete message containing URL for security
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass
            
    async def cog_unload(self):
        """Close session when cog is unloaded"""
        if self.webhook_session:
            await self.webhook_session.close()
