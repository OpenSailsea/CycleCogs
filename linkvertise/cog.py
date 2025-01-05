from typing import Optional
import discord
from discord.ext import commands
from linkvertise import LinkvertiseClient
from discord import Webhook, SyncWebhook
import aiohttp
from .utils import extract_urls, convert_to_linkvertise

FOOTER_TEXT = "\n---\n*Links in this message have been converted to Linkvertise links. Support this server to whitelist your messages.*"

class LinkvertiseCog(commands.Cog):
    """Convert message links to Linkvertise links"""
    
    def __init__(self, bot):
        self.bot = bot
        self.linkvertise_client = LinkvertiseClient()
        self.whitelisted_role_id = None
        self.webhook_url = None
        self.webhook_session = None
        self.account_id = None
    
    async def cog_load(self):
        """Initialize Linkvertise client when cog is loaded"""
        # Get config
        config = await self.bot.get_cog_config(self)
        if not config:
            raise commands.ExtensionError("Configuration not found")
            
        account_id = config.get("account_id")
        if not account_id:
            raise commands.ExtensionError("Linkvertise account ID not set")
            
        self.whitelisted_role_id = config.get("whitelisted_role_id")
        self.webhook_url = config.get("webhook_url")
        self.account_id = account_id
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
            
        # Check whitelist role
        if self.whitelisted_role_id:
            member_roles = [role.id for role in message.author.roles]
            if self.whitelisted_role_id in member_roles:
                return
                
        # Extract and check links
        url_infos = extract_urls(message.content)
        if not url_infos:
            return
            
        # Convert all links
        new_content = message.content
        offset = 0
        
        for url, start, end in url_infos:
            new_url = convert_to_linkvertise(url, self.linkvertise_client, self.account_id)
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
            
            if self.webhook_url and self.webhook_session:
                # Send message using webhook
                async with aiohttp.ClientSession() as session:
                    webhook = Webhook.from_url(self.webhook_url, session=session)
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
    @commands.has_permissions(administrator=True)
    async def linkvertise_group(self, ctx: commands.Context):
        """Linkvertise settings command group"""
        await ctx.send_help(ctx.command)
    
    @linkvertise_group.command(name="setrole")
    @commands.has_permissions(administrator=True)
    async def set_whitelisted_role(self, ctx: commands.Context, role: discord.Role):
        """Set whitelist role"""
        config = await self.bot.get_cog_config(self)
        config["whitelisted_role_id"] = role.id
        await self.bot.save_cog_config(self, config)
        self.whitelisted_role_id = role.id
        await ctx.send(f"Set {role.name} as whitelist role")
    
    @linkvertise_group.command(name="setid")
    @commands.has_permissions(administrator=True)
    async def set_account_id(self, ctx: commands.Context, account_id: int):
        """Set Linkvertise account ID"""
        config = await self.bot.get_cog_config(self)
        config["account_id"] = account_id
        await self.bot.save_cog_config(self, config)
        self.account_id = account_id
        await ctx.send("Updated Linkvertise account ID")
            
    @linkvertise_group.command(name="setwebhook")
    @commands.has_permissions(administrator=True)
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
            
        config = await self.bot.get_cog_config(self)
        config["webhook_url"] = webhook_url
        await self.bot.save_cog_config(self, config)
        self.webhook_url = webhook_url
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
