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

        try:
            # Send the announcement
            message_content = f"{ping}\n{content}" if ping else content
            await interaction.response.send_message(
                message_content,
                allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=True)
            )
        except discord.errors.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Failed to send announcement: {str(e)}",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(Broadcaster(bot))
    print("✅ Broadcaster cog loaded with announce command")
