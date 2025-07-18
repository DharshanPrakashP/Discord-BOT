import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

WELCOME_CHANNEL_ID = None
LEAVE_CHANNEL_ID = None

# ---------- SERVER STATS ----------
async def update_server_stats(guild: discord.Guild):
    category_name = "📊 SERVER STATS 📊"
    voice_names = {
        "All Members": lambda g: f"All Members: {g.member_count}",
        "Members": lambda g: f"Members: {len([m for m in g.members if not m.bot])}",
        "Bots": lambda g: f"Bots: {len([m for m in g.members if m.bot])}"
    }

    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        try:
            category = await guild.create_category(category_name)
        except discord.Forbidden:
            print("Bot lacks permission to create categories.")
            return

    for base_name, name_fn in voice_names.items():
        new_name = name_fn(guild)
        existing = next((vc for vc in category.voice_channels if vc.name.startswith(base_name)), None)

        if existing:
            if existing.name != new_name:
                await existing.edit(name=new_name)
        else:
            await guild.create_voice_channel(new_name, category=category)

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")
    for guild in bot.guilds:
        await update_server_stats(guild)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print("Sync failed:", e)

# ---------- WELCOME / LEAVE ----------
@bot.event
async def on_member_join(member):
    if WELCOME_CHANNEL_ID:
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            await channel.send(f"👋 Welcome {member.mention} to **{member.guild.name}**!")

@bot.event
async def on_member_remove(member):
    if LEAVE_CHANNEL_ID:
        channel = bot.get_channel(LEAVE_CHANNEL_ID)
        if channel:
            await channel.send(f"😢 {member.name} has left **{member.guild.name}**.")

# ---------- UI FOR DROPDOWNS ----------
class ChannelSelect(ui.Select):
    def __init__(self, ctx, target: str):
        self.ctx = ctx
        self.target = target
        options = [
            discord.SelectOption(label=channel.name, value=str(channel.id))
            for channel in ctx.guild.text_channels
        ]
        super().__init__(placeholder="Choose a channel...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        global WELCOME_CHANNEL_ID, LEAVE_CHANNEL_ID

        selected_id = int(self.values[0])
        if self.target == "welcome":
            WELCOME_CHANNEL_ID = selected_id
            await interaction.response.send_message(f"✅ Welcome channel set to <#{selected_id}>", ephemeral=True)
        elif self.target == "leave":
            LEAVE_CHANNEL_ID = selected_id
            await interaction.response.send_message(f"✅ Leave channel set to <#{selected_id}>", ephemeral=True)

class ChannelSetupView(ui.View):
    def __init__(self, ctx, target):
        super().__init__(timeout=60)
        self.add_item(ChannelSelect(ctx, target))

# ---------- COMMANDS ----------
@bot.tree.command(name="setup_welcome", description="Set the welcome channel")
async def setup_welcome(interaction: discord.Interaction):
    await interaction.response.send_message("🔧 Select the Welcome Channel:", view=ChannelSetupView(interaction, "welcome"), ephemeral=True)

@bot.tree.command(name="setup_leave", description="Set the leave channel")
async def setup_leave(interaction: discord.Interaction):
    await interaction.response.send_message("🔧 Select the Leave Channel:", view=ChannelSetupView(interaction, "leave"), ephemeral=True)

# ---------- MOD PANEL WITH TAGGING ----------
@bot.tree.command(name="modpanel", description="Send an announcement with tagging")
@app_commands.describe(content="The announcement content")
async def modpanel(interaction: discord.Interaction, content: str):
    view = AnnouncementChannelView(interaction, content)
    await interaction.response.send_message("📢 Select the channel to send the announcement:", view=view, ephemeral=True)

class AnnouncementChannelSelect(ui.Select):
    def __init__(self, ctx, content):
        self.ctx = ctx
        self.content = content
        options = [
            discord.SelectOption(label=channel.name, value=str(channel.id))
            for channel in ctx.guild.text_channels
        ]
        super().__init__(placeholder="Pick a channel...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel = self.ctx.guild.get_channel(int(self.values[0]))
        if channel:
            # Replace @everyone / @user placeholders manually if needed
            msg = self.content.replace("@everyone", "@everyone")
            msg = msg.replace("@here", "@here")
            msg = msg.replace("{user}", interaction.user.mention)

            await channel.send(msg)
            await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Could not find channel.", ephemeral=True)

class AnnouncementChannelView(ui.View):
    def __init__(self, ctx, content):
        super().__init__(timeout=60)
        self.add_item(AnnouncementChannelSelect(ctx, content))

# ---------- RUN ----------
bot.run(TOKEN)
