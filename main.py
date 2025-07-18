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

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------ MOD PANEL ------------------------
class ModDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="\ud83d\udce2 Announcement", description="Send a server-wide announcement"),
            # Future options here
        ]
        super().__init__(placeholder="Select a moderator function...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0].startswith("\ud83d\udce2"):
            await interaction.response.send_modal(AnnouncementModal())

class ModDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ModDropdown())

class AnnouncementModal(discord.ui.Modal, title="\ud83d\udce2 Send Announcement"):
    message = discord.ui.TextInput(label="Announcement Message", style=discord.TextStyle.paragraph)
    channel_id = discord.ui.TextInput(label="Target Channel ID", placeholder="123456789012345678", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel = bot.get_channel(int(self.channel_id.value))
            if not isinstance(channel, discord.TextChannel):
                raise ValueError("Invalid channel")
            await channel.send(f"\ud83d\udce2 **Announcement:**\n{self.message.value}")
            await interaction.response.send_message("\u2705 Announcement sent!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"\u274c Failed: {e}", ephemeral=True)

@bot.tree.command(name="modpanel", description="Open moderator tools")
async def modpanel(interaction: discord.Interaction):
    if interaction.channel.id != MOD_FUNCTIONS_CHANNEL_ID:
        await interaction.response.send_message("\u274c Use this command in the mod tools channel.", ephemeral=True)
        return
    await interaction.response.send_message("**Moderator Functions**", view=ModDropdownView(), ephemeral=True)

# ------------------------ EVENTS ------------------------
@bot.event
async def on_ready():
    print(f"\u2705 Logged in as {bot.user}")
    await bot.tree.sync()
    try:
        await setup_server_stats()
        refresh_server_stats.start()
    except discord.Forbidden:
        print("\u274c Bot does not have permission to manage channels.")

@bot.event
async def on_member_join(member):
    await send_welcome_image(member, bot.get_channel(WELCOME_CHANNEL_ID))
    await update_server_stats(member.guild)

@bot.event
async def on_member_remove(member):
    await send_leave_message(member, bot.get_channel(LEAVING_CHANNEL_ID))
    await update_server_stats(member.guild)

# ------------------------ WELCOME / LEAVE IMAGE ------------------------
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
        except Exception:
            text_font = ImageFont.load_default()
        draw.text(TEXT_POSITION, TEXT_BELOW_USERNAME, font=text_font, fill=TEXT_COLOR)

    buffer = BytesIO()
    bg.save(buffer, format="PNG")
    buffer.seek(0)

    file = discord.File(fp=buffer, filename="welcome.png")
    embed = discord.Embed(
        title=f"\ud83d\udc4b Welcome to Only Gamers, {member.name}!",
        description="\ud83c\udfae You're now part of the grind squad! Check rules and roles!",
        color=discord.Color.blue()
    )
    embed.set_image(url="attachment://welcome.png")
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
    embed.add_field(name="\ud83d\udcc5 Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name="\ud83d\udd39 You are member", value=str(member.guild.member_count), inline=True)

    await channel.send(content=member.mention, file=file, embed=embed)

async def send_leave_message(member, channel):
    embed = discord.Embed(
        title=f"\ud83d\udc4b {member.name} just left Only Gamers.",
        description="\ud83d\ude22 Another warrior has logged off...",
        color=discord.Color.red()
    )
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
    embed.add_field(name="\ud83d\udcc5 Left", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)
    embed.add_field(name="\ud83d\udc65 Members Remaining", value=str(member.guild.member_count), inline=True)
    await channel.send(embed=embed)

# ------------------------ SERVER STATS ------------------------
@tasks.loop(minutes=5)
async def refresh_server_stats():
    for guild in bot.guilds:
        try:
            await update_server_stats(guild)
        except discord.Forbidden:
            print(f"\u274c Missing permissions to update stats in {guild.name}")

async def setup_server_stats():
    for guild in bot.guilds:
        await update_server_stats(guild)

async def update_server_stats(guild):
    category_name = "\ud83d\udcca SERVER STATS \ud83d\udcca"
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
        existing = discord.utils.get(category.voice_channels, name=new_name)

        if existing:
            if existing.name != new_name:
                await existing.edit(name=new_name)
        else:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False)
            }
            await guild.create_voice_channel(new_name, category=category, overwrites=overwrites)

# ------------------------ DEBUG COMMANDS ------------------------
@bot.command(name="testwelcome")
async def test_welcome(ctx):
    await send_welcome_image(ctx.author, ctx.channel)

@bot.command(name="testleave")
async def test_leave(ctx):
    await send_leave_message(ctx.author, ctx.channel)

@bot.command(name="refreshstats")
async def manual_refresh(ctx):
    await update_server_stats(ctx.guild)
    await ctx.send("\u2705 Server stats refreshed.")

# ------------------------ KEEP ALIVE ------------------------
keep_alive()
bot.run(TOKEN)
