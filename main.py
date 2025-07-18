import discord
from discord.ext import commands, tasks
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import requests
import os
from dotenv import load_dotenv
from keep_alive import keep_alive

# ------------------------ LOAD ENV ------------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))
LEAVING_CHANNEL_ID = int(os.getenv("LEAVING_CHANNEL_ID"))
MOD_FUNCTIONS_CHANNEL_ID = int(os.getenv("MOD_FUNCTIONS_CHANNEL_ID"))

BACKGROUND_PATH = "./assets/OG_Welcome.png"
FONT_PATH = "./assets/arial.ttf"

AVATAR_SIZE = (170, 170)
AVATAR_POSITION = (836, 798)

TEXT_BELOW_USERNAME = ""
TEXT_POSITION = (130, 270)
TEXT_FONT_SIZE = 38
TEXT_COLOR = "white"

ALLOWED_ROLES = ["Admin", "Mod"]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------ DROPDOWN UI ------------------------
class ModDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="📢 Announcement", description="Send a server-wide announcement"),
        ]
        super().__init__(placeholder="Select a moderator function...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0].startswith("📢"):
            await interaction.response.send_modal(AnnouncementModal())

class ModDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ModDropdown())

class AnnouncementModal(discord.ui.Modal, title="📢 Send Announcement"):
    message = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        # Replace placeholders
        content = self.message.value
        content = content.replace("{user}", interaction.user.mention)
        await interaction.channel.send(content)
        await interaction.response.send_message("✅ Announcement sent!", ephemeral=True)

# ------------------------ SLASH COMMANDS ------------------------
@bot.tree.command(name="modpanel", description="Open moderator tools")
async def modpanel(interaction: discord.Interaction):
    if interaction.channel.id != MOD_FUNCTIONS_CHANNEL_ID:
        await interaction.response.send_message("❌ Use this in the mod tools channel.", ephemeral=True)
        return
    await interaction.response.send_message("**Moderator Functions**", view=ModDropdownView(), ephemeral=True)

@bot.tree.command(name="announcement", description="Send an announcement in this channel")
@app_commands.describe(message="The announcement content")
async def announcement(interaction: discord.Interaction, message: str):
    # Role-check
    if not any(role.name in ALLOWED_ROLES for role in interaction.user.roles):
        await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)
        return

    # Replace special placeholders
    content = message.replace("{user}", interaction.user.mention).replace("@everyone", "@everyone").replace("@here", "@here")
    await interaction.channel.send(content)
    await interaction.response.send_message("✅ Announcement sent.", ephemeral=True)

@bot.tree.command(name="testwelcome", description="Simulate a welcome event")
async def test_welcome(interaction: discord.Interaction):
    await send_welcome_image(interaction.user, interaction.channel)
    await interaction.response.send_message("✅ Sent test welcome message.", ephemeral=True)

@bot.tree.command(name="testleave", description="Simulate a leave event")
async def test_leave(interaction: discord.Interaction):
    await send_leave_message(interaction.user, interaction.channel)
    await interaction.response.send_message("✅ Sent test leave message.", ephemeral=True)

@bot.tree.command(name="refreshstats", description="Manually refresh server stats")
async def manual_refresh(interaction: discord.Interaction):
    await update_server_stats(interaction.guild)
    await interaction.response.send_message("✅ Server stats updated.", ephemeral=True)

# ------------------------ WELCOME IMAGE ------------------------
async def send_welcome_image(member, channel):
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(BytesIO(response.content)).convert("RGBA")
    avatar = avatar.resize(AVATAR_SIZE)

    mask = Image.new("L", AVATAR_SIZE, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, AVATAR_SIZE[0], AVATAR_SIZE[1]), fill=255)
    avatar.putalpha(mask)

    bg = Image.open(BACKGROUND_PATH).convert("RGBA")
    bg.paste(avatar, AVATAR_POSITION, avatar)

    if TEXT_BELOW_USERNAME:
        draw = ImageDraw.Draw(bg)
        try:
            text_font = ImageFont.truetype(FONT_PATH, TEXT_FONT_SIZE)
        except Exception as e:
            print(f"⚠️ Font load failed: {e}. Using default font.")
            text_font = ImageFont.load_default()
        draw.text(TEXT_POSITION, TEXT_BELOW_USERNAME, font=text_font, fill=TEXT_COLOR)

    buffer = BytesIO()
    bg.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(fp=buffer, filename="welcome.png")
    embed = discord.Embed(
        title=f"👋 Welcome to Only Gamers, {member.name}!",
        description="🎮 You're now part of the grind squad! Make sure to check the rules and roles. Let’s dominate together!",
        color=discord.Color.blue()
    )
    embed.set_image(url="attachment://welcome.png")
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
    embed.add_field(name="📅 Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name="🔢 You are member", value=str(member.guild.member_count), inline=True)

    await channel.send(content=member.mention, file=file, embed=embed)

# ------------------------ LEAVE MESSAGE ------------------------
async def send_leave_message(member, channel):
    embed = discord.Embed(
        title=f"👋 {member.name} just left Only Gamers.",
        description="😢 Another warrior has logged off...",
        color=discord.Color.red()
    )
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
    embed.add_field(name="📅 Left", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)
    embed.add_field(name="👥 Members Remaining", value=str(member.guild.member_count), inline=True)

    await channel.send(embed=embed)

# ------------------------ SERVER STATS ------------------------
@tasks.loop(minutes=5)
async def refresh_server_stats():
    for guild in bot.guilds:
        await update_server_stats(guild)

async def setup_server_stats():
    for guild in bot.guilds:
        await update_server_stats(guild)

async def update_server_stats(guild):
    category_name = "📊 SERVER STATS 📊"
    voice_names = {
        "All Members": lambda g: f"All Members: {g.member_count}",
        "Members": lambda g: f"Members: {len([m for m in g.members if not m.bot])}",
        "Bots": lambda g: f"Bots: {len([m for m in g.members if m.bot])}"
    }

    category = discord.utils.get(guild.categories, name=category_name)
    if not category:
        category = await guild.create_category(category_name)

    for base_name, name_fn in voice_names.items():
        new_name = name_fn(guild)
        existing = next((vc for vc in category.voice_channels if vc.name.startswith(base_name)), None)

        if existing:
            if existing.name != new_name:
                await existing.edit(name=new_name)
        else:
            await guild.create_voice_channel(new_name, category=category)

# ------------------------ EVENTS ------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await bot.tree.sync()
    try:
        await setup_server_stats()
        refresh_server_stats.start()
    except discord.Forbidden:
        print("❌ Permission error during server stats setup.")

@bot.event
async def on_member_join(member):
    await send_welcome_image(member, bot.get_channel(WELCOME_CHANNEL_ID))
    await update_server_stats(member.guild)

@bot.event
async def on_member_remove(member):
    await send_leave_message(member, bot.get_channel(LEAVING_CHANNEL_ID))
    await update_server_stats(member.guild)

# ------------------------ KEEP ALIVE ------------------------
keep_alive()
bot.run(TOKEN)
