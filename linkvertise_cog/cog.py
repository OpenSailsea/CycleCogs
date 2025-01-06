from typing import Optional
import discord
from redbot.core import commands, Config
from linkvertise import LinkvertiseClient
from discord import Webhook, SyncWebhook
import aiohttp
from .utils import extract_urls, convert_to_linkvertise

DEFAULT_FOOTER = "\n\n> *The link in this message has been converted. You need to watch an advertisement provided by our sponsors to continue accessing the link.\nBy boosting this server, you can have your messages added to the link whitelist.\nIf you believe this link should not have been converted, please contact our staff team.*"

class LinkvertiseCog(commands.Cog):
    """Convert message links to Linkvertise links"""
    
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_guild = {
            "account_id": None,
            "whitelisted_role_id": None,
            "footer_text": DEFAULT_FOOTER,
            "whitelisted_domains": [],
            "shortio_api_key": None,
            "shortio_domain": None
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
                
        # Get whitelist and shortio settings
        whitelisted_domains = await guild_config.whitelisted_domains()
        shortio_api_key = await guild_config.shortio_api_key()
        shortio_domain = await guild_config.shortio_domain()
        
        # Extract and check links
        url_infos = extract_urls(message.content, whitelisted_domains)
        if not url_infos:
            return
            
        # Convert all links
        new_content = message.content
        offset = 0
        
        for url, start, end in url_infos:
            new_url = await convert_to_linkvertise(
                url, 
                self.linkvertise_client, 
                account_id,
                shortio_api_key,
                shortio_domain
            )
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
            
        # Add footer text
        footer_text = "\n\n" + await guild_config.footer_text()
        new_content += footer_text
        
        # Delete original message and send new one
        try:
            await message.delete()
            
            try:
                # Create webhook
                webhook = await message.channel.create_webhook(
                    name=f"{message.author.display_name}",
                    reason="Temporary webhook for message conversion"
                )
                
                # Send message through webhook
                await webhook.send(
                    content=new_content,
                    username=message.author.display_name,
                    avatar_url=message.author.display_avatar.url,
                    allowed_mentions=discord.AllowedMentions.none()
                )
                
                # Delete webhook immediately
                await webhook.delete()
            except discord.Forbidden:
                # Fallback to normal message if no webhook permission
                await message.channel.send(
                    new_content,
                    allowed_mentions=discord.AllowedMentions.none()
                )
        except discord.Forbidden:
            # If no permission to delete, reply with converted links
            await message.reply(
                f"Links converted: {new_url}" + footer_text,
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
    
    @linkvertise_group.command(name="setfooter")
    @commands.admin_or_permissions(administrator=True)
    async def set_footer(self, ctx: commands.Context, *, text: str):
        """Set custom footer text for converted messages"""
        await self.config.guild(ctx.guild).footer_text.set(text)
        await ctx.send("Updated footer text")
    
    @linkvertise_group.command(name="resetfooter")
    @commands.admin_or_permissions(administrator=True)
    async def reset_footer(self, ctx: commands.Context):
        """Reset footer text to default"""
        await self.config.guild(ctx.guild).footer_text.set(DEFAULT_FOOTER)
        await ctx.send("Reset footer text to default")

    @linkvertise_group.command(name="whitelist")
    @commands.admin_or_permissions(administrator=True)
    async def manage_whitelist(self, ctx: commands.Context, action: str, domain: Optional[str] = None):
        """Manage domain whitelist
        
        Examples:
        [p]linkvertise whitelist add example.com
        [p]linkvertise whitelist remove example.com
        [p]linkvertise whitelist list
        """
        if action.lower() not in ["add", "remove", "list"]:
            await ctx.send("Invalid action. Available actions: add, remove, list")
            return

        whitelisted_domains = await self.config.guild(ctx.guild).whitelisted_domains()
        
        if action.lower() == "list":
            if not whitelisted_domains:
                await ctx.send("Whitelist is empty")
            else:
                domains_list = "\n".join(whitelisted_domains)
                await ctx.send(f"Whitelisted domains:\n{domains_list}")
            return
            
        if not domain:
            await ctx.send("Please provide a domain")
            return
            
        if action.lower() == "add":
            if domain in whitelisted_domains:
                await ctx.send(f"{domain} is already whitelisted")
            else:
                whitelisted_domains.append(domain)
                await self.config.guild(ctx.guild).whitelisted_domains.set(whitelisted_domains)
                await ctx.send(f"Added {domain} to whitelist")
        elif action.lower() == "remove":
            if domain not in whitelisted_domains:
                await ctx.send(f"{domain} is not in whitelist")
            else:
                whitelisted_domains.remove(domain)
                await self.config.guild(ctx.guild).whitelisted_domains.set(whitelisted_domains)
                await ctx.send(f"Removed {domain} from whitelist")

    @linkvertise_group.command(name="shortio")
    @commands.admin_or_permissions(administrator=True)
    async def set_shortio(self, ctx: commands.Context, api_key: str, domain: str):
        """Set Short.io API configuration
        
        Example:
        [p]linkvertise shortio sk_xxxxx your-domain.com
        """
        await self.config.guild(ctx.guild).shortio_api_key.set(api_key)
        await self.config.guild(ctx.guild).shortio_domain.set(domain)
        await ctx.send("Updated Short.io settings")
            
    async def cog_unload(self):
        """Close session when cog is unloaded"""
        if self.webhook_session:
            await self.webhook_session.close()
