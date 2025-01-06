"""
Verification system cog for Red-DiscordBot.
Provides button-based verification with role assignment functionality.
"""
import discord
from redbot.core import commands, Config
from redbot.core.bot import Red
import asyncio

class VerifyView(discord.ui.View):
    """View containing the verifi
    cation button"""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(VerifyButton())

class VerifyButton(discord.ui.Button):
    """Button for verification panel"""
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.green,
            label="Verify",
            custom_id="verify_button"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle button click for verification"""
        # Get the cog instance
        cog = interaction.client.get_cog("Verify")
        if not cog:
            await interaction.response.send_message("Error: Verification system is not properly loaded.", ephemeral=True)
            return

        # Get verification roles
        guild_roles = await cog.config.guild(interaction.guild).roles()
        if not guild_roles:
            await interaction.response.send_message("Error: No verification roles are set up.", ephemeral=True)
            return

        try:
            # Send initial success message
            await interaction.response.send_message("✅ Verification successful! Assigning roles...", ephemeral=True)
            
            # Get the roles to assign
            roles_to_assign = []
            for role_id in guild_roles:
                role = interaction.guild.get_role(role_id)
                if role:
                    roles_to_assign.append(role)

            # Add roles after a short delay
            await asyncio.sleep(3)
            await interaction.user.add_roles(*roles_to_assign, reason="Verification system")
            
            # Delete the success message
            await interaction.delete_original_response()
        except discord.Forbidden:
            await interaction.edit_original_response(content="Error: I don't have permission to assign roles.")
        except Exception as e:
            await interaction.edit_original_response(content=f"An error occurred: {str(e)}")

class Verify(commands.Cog):
    """
    A verification system with button interaction and role assignment.
    
    Features:
    - Button-based verification
    - Multiple role assignment
    - Customizable verification panel
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=8927348924,  # Unique identifier for config
            force_registration=True
        )
        
        # Default guild settings
        default_guild = {
            "roles": []  # List of role IDs to assign upon verification
        }
        
        self.config.register_guild(**default_guild)
        
        # Add persistent view
        self.persistent_views_added = False
        
    async def cog_load(self) -> None:
        """
        Called when the cog is loaded.
        Add persistent view for the verification button.
        """
        if not self.persistent_views_added:
            self.bot.add_view(VerifyView())
            self.persistent_views_added = True

    @commands.group(name="verify")
    @commands.guild_only()
    @commands.admin_or_permissions(administrator=True)
    async def _verify(self, ctx: commands.Context):
        """Verification system configuration commands."""
        pass

    @_verify.command(name="panel")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def panel(
        self,
        ctx: commands.Context,
        *roles: discord.Role
    ):
        """
        Create a verification panel in the current channel.
        
        Example:
        [p]verify panel @role1 @role2
        """
        if not roles:
            await ctx.send("Error: Please provide at least one role to assign upon verification.")
            return

        # Store roles for this guild
        await self.config.guild(ctx.guild).roles.set([role.id for role in roles])

        # Create embed for verification panel
        embed = discord.Embed(
            title="Server Verification",
            description="Click the button below to verify yourself and gain access to the server.",
            color=discord.Color.blue()
        )
        
        # Send panel with button
        await ctx.message.delete()
        await ctx.send(embed=embed, view=VerifyView())

    @panel.error
    async def panel_error(self, ctx: commands.Context, error: commands.CommandError):
        """Error handler for the panel command"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
        elif isinstance(error, commands.NoPrivateMessage):
            await ctx.send("This command cannot be used in private messages.")
        else:
            await ctx.send(f"An error occurred: {str(error)}")
