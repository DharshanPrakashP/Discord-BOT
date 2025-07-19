import discord
from discord.ext import commands
from discord import app_commands

class Broadcaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="announce",
        description="Broadcast a message with optional @ping"
    )
    @app_commands.describe(
        content="The message you want to send",
        ping="Whom to ping (e.g. @everyone, @here, or a user)"
    )
    async def announce(self, interaction: discord.Interaction, content: str, ping: str = ""):
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return

        # Defer the response since we might take a moment to process
        await interaction.response.defer()

        try:
            # Send the announcement
            message_content = f"{ping}\n{content}" if ping else content
            await interaction.followup.send(
                message_content,
                allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=True)
            )
        except discord.errors.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to send announcement: {str(e)}",
                ephemeral=True
            )

    async def cog_load(self):
        """Called when the cog is loaded"""
        print(f"✅ Loaded {self.__class__.__name__} cog with slash commands")

# ✅ Keep this
async def setup(bot: commands.Bot):
    await bot.add_cog(Broadcaster(bot))
