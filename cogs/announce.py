import discord
from discord.ext import commands
from discord import app_commands

class Broadcaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="anounce", description="Broadcast a message in this channel.")
    @app_commands.describe(
        content="The message to broadcast",
        ping="Optional: everyone, here, or mention a user"
    )
    async def anounce(self, interaction: discord.Interaction, content: str, ping: str = None):
        ping_text = ""

        # Support @everyone / @here / raw user mentions
        if ping == "everyone":
            ping_text = "@everyone"
        elif ping == "here":
            ping_text = "@here"
        elif ping and ping.startswith("<@"):
            ping_text = ping  # user mention like <@1234>

        await interaction.channel.send(f"{ping_text} {content}".strip())
        await interaction.response.send_message("✅ Announcement sent!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Broadcaster(bot))

