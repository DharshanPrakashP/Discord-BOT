import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import requests
from dotenv import load_dotenv
import os
from keep_alive import keep_alive

# ------------------------ LOAD ENV ------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))

# ------------------------ CONFIG SECTION ------------------------

BACKGROUND_PATH = "./assets/OG_Welcome.png"
FONT_PATH = "./assets/arial.ttf"  # Make sure this exists or use fallback below

AVATAR_SIZE = (170, 170)
AVATAR_POSITION = (836, 798)

USERNAME_POSITION = (375, 75)
USERNAME_FONT_SIZE = 44
USERNAME_COLOR = "white"

TEXT_BELOW_USERNAME = ""
TEXT_POSITION = (130, 270)
TEXT_FONT_SIZE = 24
TEXT_COLOR = "white"

# ------------------------ BOT SETUP ------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    await send_welcome_image(member, bot.get_channel(WELCOME_CHANNEL_ID))

@bot.command(name="testwelcome")
async def test_welcome(ctx):
    """Test the welcome image using your avatar."""
    await send_welcome_image(ctx.author, ctx.channel)

# ------------------------ WELCOME IMAGE GENERATOR ------------------------

async def send_welcome_image(member, channel):
    # Fetch avatar
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(BytesIO(response.content)).convert("RGBA")
    avatar = avatar.resize(AVATAR_SIZE)

    # Create circular mask
    mask = Image.new("L", AVATAR_SIZE, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, AVATAR_SIZE[0], AVATAR_SIZE[1]), fill=255)
    avatar.putalpha(mask)

    # Load background and paste avatar
    bg = Image.open(BACKGROUND_PATH).convert("RGBA")
    bg.paste(avatar, AVATAR_POSITION, avatar)

    # Add username text
    draw = ImageDraw.Draw(bg)
    try:
        username_font = ImageFont.truetype(FONT_PATH, USERNAME_FONT_SIZE)
        text_font = ImageFont.truetype(FONT_PATH, TEXT_FONT_SIZE)
    except Exception as e:
        print(f"⚠️ Font load failed: {e}. Using default font.")
        username_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    draw.text(USERNAME_POSITION, member.name.upper(), font=username_font, fill=USERNAME_COLOR)
    draw.text(TEXT_POSITION, TEXT_BELOW_USERNAME, font=text_font, fill=TEXT_COLOR)

    # Save image to memory buffer
    buffer = BytesIO()
    bg.save(buffer, format="PNG")
    buffer.seek(0)

    # Create file & embed
    file = discord.File(fp=buffer, filename="welcome.png")
    embed = discord.Embed(
        title=f"👋 Welcome to Only Gamers, {member.name}!",
        description="🎮 You're now part of the grind squad! Make sure to check the rules and roles. Let’s dominate together!",
        color=discord.Color.blue()
    )
    embed.set_image(url="attachment://welcome.png")
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")

    # 📅 Join Time
    embed.add_field(name="📅 Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)

    # 👥 Member Count
    member_number = member.guild.member_count
    embed.add_field(name="🔢 You are member", value=str(member_number), inline=True)

    # Send embed with image and mention
    await channel.send(content=member.mention, file=file, embed=embed)

# ------------------------ RUN BOT ------------------------
keep_alive()
bot.run(TOKEN)
