import discord
from discord.ext import commands
from discord import app_commands

class Broadcaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="anounce", description="Broadcast a message in this channel")
    @app_commands.describe(content="The message you want to broadcast")
    async def anounce(self, interaction: discord.Interaction, content: str):
        await interaction.response.send_message(content)

async def setup(bot):
    await bot.add_cog(Broadcaster(bot))
