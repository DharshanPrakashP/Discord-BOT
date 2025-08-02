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
intents.moderation = True  # For timeout/ban actions

bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------ LOAD COGS ------------------------
async def load_cogs():
    try:
        await bot.load_extension("cogs.announce")
        print("✅ Successfully loaded announce cog")
    except Exception as e:
        print(f"❌ Failed to load announce cog: {e}")
    
    try:
        await bot.load_extension("cogs.moderation")
        print("✅ Successfully loaded moderation cog")
    except Exception as e:
        print(f"❌ Failed to load moderation cog: {e}")

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
        print("✅ Server stats system started successfully")
    except discord.Forbidden:
        print("⚠️  Bot does not have permission to manage channels. Server stats disabled.")
        print("💡 Use !getinvite or /invite to get a new invite link with proper permissions.")
    except Exception as e:
        print(f"❌ Error setting up server stats: {e}")

@bot.event
async def on_member_join(member):
    # Only send welcome message if we can find the welcome channel
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        try:
            await send_welcome_image(member, welcome_channel)
        except Exception as e:
            print(f"❌ Error sending welcome message: {e}")
    else:
        print(f"⚠️  Welcome channel not found (ID: {WELCOME_CHANNEL_ID})")
    
    # Update server stats
    try:
        await update_server_stats(member.guild)
    except Exception as e:
        print(f"❌ Error updating server stats: {e}")

@bot.event
async def on_member_remove(member):
    # Only send leave message if we can find the leaving channel
    leaving_channel = bot.get_channel(LEAVING_CHANNEL_ID)
    if leaving_channel:
        try:
            await send_leave_message(member, leaving_channel)
        except Exception as e:
            print(f"❌ Error sending leave message: {e}")
    else:
        print(f"⚠️  Leaving channel not found (ID: {LEAVING_CHANNEL_ID})")
    
    # Update server stats
    try:
        await update_server_stats(member.guild)
    except Exception as e:
        print(f"❌ Error updating server stats: {e}")

# ------------------------ WELCOME / LEAVE IMAGE ------------------------
async def send_welcome_image(member, channel):
    # Safety check for channel
    if not channel:
        print(f"❌ Cannot send welcome message: channel is None")
        return
        
    if not channel.permissions_for(member.guild.me).send_messages:
        print(f"❌ Cannot send welcome message: no permission in {channel.name}")
        return
        
    try:
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
        print(f"✅ Sent welcome message for {member.name} to {channel.name}")
        
    except Exception as e:
        print(f"❌ Error in send_welcome_image: {e}")

async def send_leave_message(member, channel):
    # Safety check for channel
    if not channel:
        print(f"❌ Cannot send leave message: channel is None")
        return
        
    if not channel.permissions_for(member.guild.me).send_messages:
        print(f"❌ Cannot send leave message: no permission in {channel.name}")
        return
        
    try:
        embed = discord.Embed(
            title=f"👋 {member.name} just left Only Gamers.",
            description="😢 Another warrior has logged off...",
            color=discord.Color.red()
        )
        embed.set_footer(text="Only Gamers • Respect. Play. Repeat.")
        embed.add_field(name="📅 Left", value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>", inline=True)
        embed.add_field(name="👥 Members Remaining", value=str(member.guild.member_count), inline=True)
        
        await channel.send(embed=embed)
        print(f"✅ Sent leave message for {member.name} to {channel.name}")
        
    except Exception as e:
        print(f"❌ Error in send_leave_message: {e}")

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
        try:
            await update_server_stats(guild)
        except discord.Forbidden:
            print(f"⚠️  Missing permissions for server stats in {guild.name}")
        except Exception as e:
            print(f"❌ Error setting up server stats in {guild.name}: {e}")

async def update_server_stats(guild):
    # Check if bot has necessary permissions
    bot_member = guild.get_member(bot.user.id)
    if not bot_member or not bot_member.guild_permissions.manage_channels:
        return  # Silently skip if no permissions
        
    category_name = "📊 SERVER STATS 📊"
    voice_names = {
        "All Members": lambda g: f"All Members: {g.member_count}",
        "Members": lambda g: f"Members: {len([m for m in g.members if not m.bot])}",
        "Bots": lambda g: f"Bots: {len([m for m in g.members if m.bot])}"
    }

    try:
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

        # Check for existing channels and clean up duplicates
        for base_name, name_fn in voice_names.items():
            new_name = name_fn(guild)
            
            # Find all channels that match the pattern (e.g., "All Members: X")
            pattern_channels = [
                ch for ch in category.voice_channels 
                if ch.name.startswith(f"{base_name}:")
            ]
            
            if pattern_channels:
                # Keep the first one, update its name if needed
                target_channel = pattern_channels[0]
                if target_channel.name != new_name:
                    await target_channel.edit(name=new_name)
                
                # Delete any duplicates
                for duplicate in pattern_channels[1:]:
                    try:
                        await duplicate.delete()
                        print(f"🗑️ Deleted duplicate stats channel: {duplicate.name}")
                    except discord.Forbidden:
                        pass
            else:
                # No existing channel, create new one
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(connect=False)
                }
                await guild.create_voice_channel(new_name, category=category, overwrites=overwrites)
                
    except discord.Forbidden:
        # Permissions were revoked during execution
        pass
    except Exception as e:
        print(f"❌ Error updating server stats in {guild.name}: {e}")

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

@bot.command(name="cleanstats")
async def clean_stats(ctx):
    """Clean up duplicate server stats channels - Admin only"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need administrator permissions to use this command.")
        return
    
    try:
        category_name = "📊 SERVER STATS 📊"
        category = discord.utils.get(ctx.guild.categories, name=category_name)
        
        if not category:
            await ctx.send("❌ No server stats category found.")
            return
        
        # Count and clean duplicates
        cleaned_count = 0
        base_names = ["All Members", "Members", "Bots"]
        
        for base_name in base_names:
            # Find all channels that match the pattern
            pattern_channels = [
                ch for ch in category.voice_channels 
                if ch.name.startswith(f"{base_name}:")
            ]
            
            if len(pattern_channels) > 1:
                # Keep the first one, delete the rest
                for duplicate in pattern_channels[1:]:
                    try:
                        await duplicate.delete()
                        cleaned_count += 1
                        print(f"🗑️ Deleted duplicate stats channel: {duplicate.name}")
                    except discord.Forbidden:
                        pass
        
        if cleaned_count > 0:
            await ctx.send(f"✅ Cleaned up {cleaned_count} duplicate server stats channels.")
            await update_server_stats(ctx.guild)  # Refresh after cleanup
        else:
            await ctx.send("✅ No duplicate server stats channels found.")
            
    except Exception as e:
        await ctx.send(f"❌ Error cleaning stats: {e}")

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

@bot.command(name="checkperms")
async def check_permissions(ctx):
    """Check bot permissions and suggest fixes"""
    bot_member = ctx.guild.get_member(bot.user.id)
    if not bot_member:
        await ctx.send("❌ Cannot find bot member in this guild.")
        return
    
    perms = bot_member.guild_permissions
    
    # Define required permissions and their purposes
    required_perms = {
        "send_messages": "Send messages",
        "embed_links": "Send embeds",
        "attach_files": "Send welcome images",
        "read_message_history": "Read messages",
        "manage_channels": "Create server stats channels",
        "manage_messages": "Delete spam/inappropriate content",
        "moderate_members": "Timeout users",
        "kick_members": "Kick users (optional)",
        "ban_members": "Ban users (optional)"
    }
    
    embed = discord.Embed(
        title="🔍 Bot Permissions Check",
        color=discord.Color.blue()
    )
    
    # Check each permission
    missing_perms = []
    working_features = []
    limited_features = []
    
    for perm_name, description in required_perms.items():
        has_perm = getattr(perms, perm_name, False)
        
        if perm_name in ["send_messages", "embed_links", "attach_files", "read_message_history"]:
            # Core permissions
            if has_perm:
                working_features.append(f"✅ {description}")
            else:
                missing_perms.append(f"❌ {description}")
        elif perm_name in ["manage_channels"]:
            # Server stats
            if has_perm:
                working_features.append(f"✅ {description} (Server stats)")
            else:
                limited_features.append(f"⚠️ {description} (Server stats disabled)")
        elif perm_name in ["manage_messages", "moderate_members"]:
            # Moderation
            if has_perm:
                working_features.append(f"✅ {description} (Moderation)")
            else:
                limited_features.append(f"⚠️ {description} (Moderation limited)")
        else:
            # Optional permissions
            if has_perm:
                working_features.append(f"✅ {description} (Optional)")
            else:
                limited_features.append(f"⚠️ {description} (Optional)")
    
    if working_features:
        embed.add_field(
            name="✅ Working Features",
            value="\n".join(working_features[:10]),  # Limit to prevent embed size issues
            inline=False
        )
    
    if limited_features:
        embed.add_field(
            name="⚠️ Limited Features",
            value="\n".join(limited_features[:10]),
            inline=False
        )
    
    if missing_perms:
        embed.add_field(
            name="❌ Missing Critical Permissions",
            value="\n".join(missing_perms[:10]),
            inline=False
        )
    
    if missing_perms or limited_features:
        embed.add_field(
            name="💡 How to Fix",
            value="Use `!getinvite` or `/invite` to get a new invite link with all required permissions, then:\n1. Kick the bot\n2. Re-invite with the new link\n3. Select all permission checkboxes",
            inline=False
        )
    
    embed.set_footer(text="Tip: Administrator permission includes all other permissions")
    await ctx.send(embed=embed)

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
        use_slash_commands=True,
        manage_messages=True,  # For moderation
        moderate_members=True,  # For timeout functionality
        kick_members=True,      # For moderation
        ban_members=True        # For severe moderation
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

@bot.command(name="testmod")
async def test_moderation(ctx):
    """Test moderation features - Admin only"""
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ You need administrator permissions to test moderation.")
        return
    
    embed = discord.Embed(
        title="🧪 Moderation Testing Guide",
        description="Here's how to test the moderation features safely:",
        color=discord.Color.orange()
    )
    
    embed.add_field(
        name="1️⃣ Test Anti-Spam (Safe Method)",
        value="• Create a test channel\n• Ask a non-admin user to send 5+ messages quickly\n• Bot should delete messages and warn the user\n• After 3 warnings, user gets 10-minute timeout",
        inline=False
    )
    
    embed.add_field(
        name="2️⃣ Test NSFW Filter",
        value="• Type a message with words like 'test porn link' (it will be deleted)\n• Bot should immediately delete and timeout for 30 minutes\n• **Warning:** This will actually trigger the filter!",
        inline=False
    )
    
    embed.add_field(
        name="3️⃣ Test Invite Link Blocking", 
        value="• Post a Discord invite link like `discord.gg/test`\n• Bot should delete message and give warning\n• After 3 warnings, user gets 1-hour timeout",
        inline=False
    )
    
    embed.add_field(
        name="4️⃣ Test Slash Commands",
        value="• `/clear 5` - Delete 5 messages\n• `/timeout @user 5 testing` - Timeout user for 5 minutes\n• `/modconfig 3 15` - Change spam detection (3 msgs in 15 sec)",
        inline=False
    )
    
    embed.add_field(
        name="5️⃣ Check Current Settings",
        value="• `!checkperms` - Check bot permissions\n• `/modconfig` - View current moderation settings\n• `!listcommands` - See all available commands",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Safety Tips",
        value="• Test in a separate channel\n• Have admin permissions ready to undo timeouts\n• Remember: Admins/mods are immune to moderation\n• Use alt accounts or ask regular members to help test",
        inline=False
    )
    
    embed.set_footer(text="Tip: Only non-admin users will trigger the moderation system")
    await ctx.send(embed=embed)

@bot.command(name="modstatus")
async def moderation_status(ctx):
    """Check moderation system status"""
    embed = discord.Embed(
        title="🛡️ Moderation System Status",
        color=discord.Color.green()
    )
    
    # Check if moderation cog is loaded
    mod_cog = bot.get_cog("ModerationCog")
    if mod_cog:
        embed.add_field(
            name="✅ Moderation Active",
            value="Anti-spam, NSFW filter, and invite blocking are running",
            inline=False
        )
        
        # Get current settings
        embed.add_field(
            name="⚙️ Current Settings",
            value=f"• Spam Threshold: {mod_cog.spam_threshold} messages\n• Spam Timeframe: {mod_cog.spam_timeframe} seconds\n• Max Warnings: {mod_cog.max_warnings}",
            inline=False
        )
        
        # Check permissions
        bot_member = ctx.guild.get_member(bot.user.id)
        if bot_member:
            perms = bot_member.guild_permissions
            mod_perms = []
            if perms.manage_messages:
                mod_perms.append("✅ Delete messages")
            else:
                mod_perms.append("❌ Delete messages")
            
            if perms.moderate_members:
                mod_perms.append("✅ Timeout users")
            else:
                mod_perms.append("❌ Timeout users")
                
            embed.add_field(
                name="🔑 Moderation Permissions",
                value="\n".join(mod_perms),
                inline=False
            )
    else:
        embed.add_field(
            name="❌ Moderation Inactive",
            value="Moderation cog is not loaded",
            inline=False
        )
    
    embed.add_field(
        name="🧪 Test Commands",
        value="• `!testmod` - Get testing guide\n• `!checkperms` - Check all permissions\n• `/modconfig` - Adjust settings (Admin only)",
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
        value="• `/announce` - Send announcements (Admin only)\n• `/botinfo` - Show this information\n• `/clear` - Clear messages (Mod only)\n• `/timeout` - Timeout users (Mod only)\n• `/modconfig` - Configure moderation (Admin only)",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Features",
        value="• Welcome messages with custom images\n• Server member statistics\n• Leave notifications\n• **Anti-spam protection**\n• **NSFW content filtering**\n• **Invite link blocking**",
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
        use_slash_commands=True,
        manage_messages=True,  # For deleting spam/inappropriate messages
        moderate_members=True,  # For timeout functionality
        kick_members=True,      # Optional: for more severe moderation
        ban_members=True        # Optional: for severe violations
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
