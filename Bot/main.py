import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import requests
from dotenv import load_dotenv
import os

# ------------------------ LOAD ENV ------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))

# ------------------------ CONFIG SECTION ------------------------

BACKGROUND_PATH = "./assets/OG_Welcome.png"
FONT_PATH = "./assets/arial.ttf"

AVATAR_SIZE = (150, 150)
AVATAR_POSITION = (185, 40)

USERNAME_POSITION = (100, 220)
USERNAME_FONT_SIZE = 28
USERNAME_COLOR = "white"

TEXT_BELOW_USERNAME = "to Only Gamers"
TEXT_POSITION = (130, 270)
TEXT_FONT_SIZE = 24
TEXT_COLOR = "white"

# ------------------------ BOT SETUP ------------------------

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

@bot.event
async def on_member_join(member):
    # Get avatar
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    response = requests.get(avatar_url)
    avatar = Image.open(BytesIO(response.content)).convert("RGBA")
    avatar = avatar.resize(AVATAR_SIZE)

    # Load background
    bg = Image.open(BACKGROUND_PATH).convert("RGBA")

    # Paste avatar
    bg.paste(avatar, AVATAR_POSITION, avatar)

    # Add text
    draw = ImageDraw.Draw(bg)
    username_font = ImageFont.truetype(FONT_PATH, USERNAME_FONT_SIZE)
    text_font = ImageFont.truetype(FONT_PATH, TEXT_FONT_SIZE)

    draw.text(USERNAME_POSITION, member.name.upper(), font=username_font, fill=USERNAME_COLOR)
    draw.text(TEXT_POSITION, TEXT_BELOW_USERNAME, font=text_font, fill=TEXT_COLOR)

    # Save to buffer
    buffer = BytesIO()
    bg.save(buffer, format="PNG")
    buffer.seek(0)

    # Send to Discord
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    await channel.send(file=discord.File(fp=buffer, filename="welcome.png"))

# ------------------------ BOT START ------------------------

bot.run(TOKEN)
