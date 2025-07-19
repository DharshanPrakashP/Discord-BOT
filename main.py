import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import requests
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import asyncio

# ------------------------ LOAD ENV ------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
WELCOME_CHANNEL_ID = int(os.getenv("WELCOME_CHANNEL_ID"))
LEAVING_CHANNEL_ID = int(os.getenv("LEAVING_CHANNEL_ID"))

BACKGROUND_PATH = "./assets/OG_Welcome.png"
FONT_PATH = "./assets/arial.ttf"

AVATAR_SIZE = (170, 170)
AVATAR_POSITION = (836, 798)

TEXT_BELOW_USERNAME = ""
TEXT_POSITION = (130, 270)
TEXT_FONT_SIZE = 38
TEXT_COLOR = "white"

# ------------------------ BOT SETUP ------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------ LOAD COGS ------------------------
async def load_cogs():
    try:
        await bot.load_extension("cogs.announce")
        print("✅ Successfully loaded announce cog")
    except Exception as e:
        print(f"❌ Failed to load announce cog: {e}")

# ------------------------ EVENTS ------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Connected to {len(bot.guilds)} guild(s)")
    
    # Load cogs first
    await load_cogs()
    
    # Wait a bit for cogs to load properly
    await asyncio.sleep(1)
    
    # Sync the command tree to register slash commands
    try:
        # First try syncing to all guilds (faster for testing)
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"✅ Synced {len(synced)} command(s) to guild: {guild.name}")
        
        # Also sync globally (takes up to 1 hour to propagate)
        global_synced = await bot.tree.sync()
        print(f"✅ Synced {len(global_synced)} global slash command(s)")
        
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    
    try:
        await setup_server_stats()
        refresh_server_stats.start()
    except discord.Forbidden:
        print("❌ Bot does not have permission to manage channels.")

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
        title=f"👋 Welcome to Only Gamers, {member.name}!",
        description="🎮 You're now part of the grind squad! Check rules and roles!",
        color=discord.Color.blue()
    )
    embed.set_image(url="attachment://welcome.png")
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
    embed.add_field(name="📅 Joined", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name="🔹 You are member", value=str(member.guild.member_count), inline=True)

    await channel.send(content=member.mention, file=file, embed=embed)

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
        try:
            await update_server_stats(guild)
        except discord.Forbidden:
            print(f"❌ Missing permissions to update stats in {guild.name}")

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
    await ctx.send("✅ Server stats refreshed.")

@bot.command(name="synccommands")
async def sync_commands(ctx):
    """Debug command to manually sync slash commands"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need administrator permissions to use this command.")
        return
    
    try:
        # Sync to current guild
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ Synced {len(synced)} command(s) to this guild!")
        
        # List the synced commands
        commands_list = [cmd.name for cmd in synced]
        if commands_list:
            await ctx.send(f"📋 Commands: {', '.join(commands_list)}")
            
    except Exception as e:
        await ctx.send(f"❌ Failed to sync commands: {e}")

@bot.command(name="listcommands")
async def list_commands(ctx):
    """Debug command to list all registered commands"""
    app_commands = bot.tree.get_commands()
    if app_commands:
        commands_list = [f"/{cmd.name} - {cmd.description}" for cmd in app_commands]
        embed = discord.Embed(
            title="📋 Registered Slash Commands",
            description="\n".join(commands_list),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ No slash commands registered!")

@bot.command(name="getinvite")
async def get_invite_link(ctx):
    """Get proper bot invite link with slash command support"""
    permissions = discord.Permissions(
        administrator=True,
        manage_channels=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_slash_commands=True
    )
    
    invite_url = discord.utils.oauth_url(
        bot.user.id,
        permissions=permissions,
        scopes=["bot", "applications.commands"]
    )
    
    embed = discord.Embed(
        title="🔗 Bot Re-invite Link",
        description="Use this link to re-invite the bot with slash command support",
        color=discord.Color.orange()
    )
    
    embed.add_field(
        name="📋 Copy This Link:",
        value=f"```{invite_url}```",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Instructions:",
        value="1. **Kick the bot** from this server first\n2. Click the link above\n3. Make sure **both** `bot` and `applications.commands` are selected\n4. Re-invite the bot\n5. Check bot profile - should show 'Supports slash commands'",
        inline=False
    )
    
    await ctx.send(embed=embed)

# ------------------------ SLASH COMMANDS ------------------------
@bot.tree.command(name="botinfo", description="Show bot information and available commands")
async def bot_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Only Gamers Bot",
        description="Welcome and server management bot for Only Gamers Discord server",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 Available Slash Commands",
        value="• `/announce` - Send announcements (Admin only)\n• `/botinfo` - Show this information",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Features",
        value="• Welcome messages with custom images\n• Server member statistics\n• Leave notifications",
        inline=False
    )
    
    embed.add_field(
        name="📊 Server Stats",
        value=f"Total Members: {interaction.guild.member_count}",
        inline=True
    )
    
    # Add bot permissions info
    bot_member = interaction.guild.get_member(bot.user.id)
    if bot_member:
        permissions = bot_member.guild_permissions
        embed.add_field(
            name="🔑 Bot Permissions",
            value=f"Admin: {permissions.administrator}\nManage Channels: {permissions.manage_channels}\nSend Messages: {permissions.send_messages}",
            inline=True
        )
    
    embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
    embed.set_thumbnail(url=bot.user.avatar.url if bot.user.avatar else None)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="invite", description="Get bot invite link with proper permissions")
async def invite_bot(interaction: discord.Interaction):
    # Calculate required permissions
    permissions = discord.Permissions(
        administrator=True,  # For easier setup, you can reduce this later
        manage_channels=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_slash_commands=True
    )
    
    invite_url = discord.utils.oauth_url(
        bot.user.id,
        permissions=permissions,
        scopes=["bot", "applications.commands"]  # Important: applications.commands for slash commands
    )
    
    embed = discord.Embed(
        title="🔗 Bot Invite Link",
        description=f"[Click here to invite the bot]({invite_url})",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="⚠️ Important",
        value="Make sure to select **both** 'bot' and 'applications.commands' scopes when inviting!",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ------------------------ MAIN ENTRY ------------------------
async def main():
    keep_alive()
    async with bot:
        # Don't load cogs here, do it in on_ready
        await bot.start(TOKEN)

asyncio.run(main())
