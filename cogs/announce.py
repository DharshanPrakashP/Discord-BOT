import discord
from discord.ext import commands
from discord import app_commands

class Broadcaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="announce", description="Broadcast a message with optional @ping")
    @app_commands.describe(content="The message you want to send", ping="Whom to ping (e.g. @everyone, @here, or a user)")
    async def announce(self, interaction: discord.Interaction, content: str, ping: str = ""):
        await interaction.response.send_message(f"{ping}\n{content}", allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=True))

    async def cog_load(self):
        # This will register the slash command to bot.tree
        self.bot.tree.add_command(self.announce)

async def setup(bot: commands.Bot):
    await bot.add_cog(Broadcaster(bot))
