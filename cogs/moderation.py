import discord
from discord.ext import commands
from discord import app_commands
import re
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
import aiohttp

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # Spam tracking
        self.user_messages = defaultdict(lambda: deque(maxlen=10))
        self.user_warnings = defaultdict(int)
        
        # Prevent multiple violations from same user at once
        self.processing_users = set()  # Track users currently being processed
        self.user_locks = defaultdict(asyncio.Lock)  # Per-user locks
        
        # Configuration
        self.spam_threshold = 5  # messages
        self.spam_timeframe = 10  # seconds
        self.max_warnings = 3
        
        # Track warning messages to prevent deletion
        self.warning_messages = set()
        
        # Regex patterns for detection
        self.invite_pattern = re.compile(r'(discord\.gg/|discord\.com/invite/|discordapp\.com/invite/)', re.IGNORECASE)
        
        # 18+ keywords (add more as needed)
        self.nsfw_keywords = [
            'porn', 'xxx', 'sex', 'nude', 'naked', 'nsfw', 'adult', 'erotic',
            'hentai', 'lesbian', 'gay', 'masturbate', 'orgasm', 'penis', 'vagina',
            'breast', 'dick', 'fuck', 'fucking', 'bitch', 'whore', 'slut', 'pussy'
        ]
        
        # 18+ domains (common adult sites)
        self.nsfw_domains = [
            'pornhub.com', 'xvideos.com', 'xnxx.com', 'redtube.com', 'youporn.com',
            'tube8.com', 'spankbang.com', 'xhamster.com', 'onlyfans.com'
        ]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild:
            return
            
        # Ignore messages from admins/mods
        if message.author.guild_permissions.administrator or message.author.guild_permissions.manage_messages:
            return
        
        # Process all checks asynchronously without blocking
        # Using asyncio.ensure_future to prevent blocking the event loop
        asyncio.ensure_future(self.process_message_moderation(message))

    async def process_message_moderation(self, message):
        """Process message moderation checks safely"""
        try:
            # Run all checks concurrently to prevent blocking
            await asyncio.gather(
                self.check_spam(message),
                self.check_nsfw_content(message),
                self.check_invite_links(message),
                return_exceptions=True  # Don't let one failure block others
            )
        except Exception as e:
            print(f"❌ Error in moderation processing for message {message.id}: {e}")

    async def check_spam(self, message):
        """Check for message spam with proper locking"""
        user_id = message.author.id
        
        # Use per-user lock to prevent race conditions
        async with self.user_locks[user_id]:
            # Skip if user is already being processed for spam
            if user_id in self.processing_users:
                return
                
            now = datetime.now()
            
            # Add message timestamp to user's message history
            self.user_messages[user_id].append(now)
            
            # Check if user sent too many messages in timeframe
            recent_messages = [
                msg_time for msg_time in self.user_messages[user_id]
                if now - msg_time <= timedelta(seconds=self.spam_timeframe)
            ]
            
            if len(recent_messages) >= self.spam_threshold:
                # Mark user as being processed
                self.processing_users.add(user_id)
                try:
                    await self.handle_spam_violation(message)
                finally:
                    # Always remove from processing set
                    self.processing_users.discard(user_id)

    async def check_nsfw_content(self, message):
        """Check for NSFW content in messages"""
        content = message.content.lower()
        
        # Check for NSFW keywords
        for keyword in self.nsfw_keywords:
            if keyword in content:
                await self.handle_nsfw_violation(message, f"NSFW keyword: {keyword}")
                return
        
        # Check for NSFW domains in URLs
        url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        urls = url_pattern.findall(content)
        
        for url in urls:
            for domain in self.nsfw_domains:
                if domain in url.lower():
                    await self.handle_nsfw_violation(message, f"NSFW domain: {domain}")
                    return

    async def check_invite_links(self, message):
        """Check for Discord invite links"""
        if self.invite_pattern.search(message.content):
            await self.handle_invite_violation(message)

    async def handle_spam_violation(self, message):
        """Handle spam violation with proper message management"""
        try:
            user_id = message.author.id
            channel = message.channel
            bot_id = self.bot.user.id
            
            # First, collect all recent spam messages from this user to delete them all
            # Only collect user messages, NOT bot messages
            spam_messages = []
            async for msg in channel.history(limit=50):
                if (msg.author.id == user_id and 
                    msg.author.id != bot_id and  # NEVER delete bot's own messages
                    not msg.author.bot and  # NEVER delete any bot messages
                    msg.id not in self.warning_messages and  # Don't delete warning messages
                    not msg.pinned):  # Don't delete pinned messages
                    spam_messages.append(msg)
                    if len(spam_messages) >= 10:  # Limit to prevent excessive deletion
                        break
            
            # Delete all spam messages at once
            deleted_count = 0
            if spam_messages:
                try:
                    await channel.delete_messages(spam_messages)
                    deleted_count = len(spam_messages)
                    print(f"🗑️ Deleted {deleted_count} spam messages from {message.author.name}")
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    # Fallback: delete messages individually
                    for msg in spam_messages:
                        try:
                            await msg.delete()
                            deleted_count += 1
                        except (discord.NotFound, discord.Forbidden):
                            pass
            
            # Add warning with thread safety
            self.user_warnings[user_id] += 1
            warnings = self.user_warnings[user_id]
            
            # Create warning embed
            embed = discord.Embed(
                title="⚠️ Spam Detected",
                description=f"{message.author.mention} has been detected spamming!",
                color=discord.Color.orange()
            )
            embed.add_field(name="Warning", value=f"{warnings}/{self.max_warnings}", inline=True)
            embed.add_field(name="Action", value=f"Deleted {deleted_count} messages", inline=True)
            embed.add_field(name="Reason", value="Sending messages too quickly", inline=False)
            
            # Send warning and protect it from deletion
            try:
                warning_msg = await channel.send(embed=embed)
                self.warning_messages.add(warning_msg.id)  # Protect from deletion
                
                # Schedule warning deletion and cleanup
                def cleanup_warning():
                    asyncio.create_task(self._cleanup_warning_message(warning_msg))
                
                asyncio.get_event_loop().call_later(15, cleanup_warning)
                
            except (discord.Forbidden, discord.HTTPException):
                pass  # Can't send message, continue with timeout
            
            # Take action based on warnings
            if warnings >= self.max_warnings:
                # Reset warnings before timeout to prevent duplicate timeouts
                self.user_warnings[user_id] = 0
                # Schedule timeout without blocking
                asyncio.create_task(self.timeout_user(message.author, message.guild, 600, "Excessive spam"))
                
        except Exception as e:
            print(f"❌ Error handling spam violation: {e}")

    async def handle_nsfw_violation(self, message, reason):
        """Handle NSFW content violation"""
        try:
            # Delete the message first
            try:
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass  # Message already deleted or no permission
            
            # Create violation embed
            embed = discord.Embed(
                title="🔞 NSFW Content Detected",
                description=f"{message.author.mention} sent inappropriate content!",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Action", value="Message deleted + 30min timeout", inline=True)
            
            # Send warning and protect it from deletion
            try:
                warning_msg = await message.channel.send(embed=embed)
                self.warning_messages.add(warning_msg.id)  # Protect from deletion
                
                # Schedule warning deletion and cleanup
                def cleanup_warning():
                    asyncio.create_task(self._cleanup_warning_message(warning_msg))
                
                asyncio.get_event_loop().call_later(20, cleanup_warning)
                
            except (discord.Forbidden, discord.HTTPException):
                pass  # Can't send message, continue with timeout
            
            # Timeout user for 30 minutes for NSFW content (don't await)
            asyncio.create_task(self.timeout_user(message.author, message.guild, 1800, f"NSFW content: {reason}"))
                
        except Exception as e:
            print(f"❌ Error handling NSFW violation: {e}")

    async def handle_invite_violation(self, message):
        """Handle Discord invite link violation"""
        try:
            # Delete the message first
            try:
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass  # Message already deleted or no permission
            
            # Add warning with thread safety
            user_id = message.author.id
            self.user_warnings[user_id] += 1
            warnings = self.user_warnings[user_id]
            
            # Create violation embed
            embed = discord.Embed(
                title="🚫 Invite Link Detected",
                description=f"{message.author.mention} sent a Discord invite link!",
                color=discord.Color.red()
            )
            embed.add_field(name="Warning", value=f"{warnings}/{self.max_warnings}", inline=True)
            embed.add_field(name="Action", value="Message deleted", inline=True)
            
            # Send warning and protect it from deletion
            try:
                warning_msg = await message.channel.send(embed=embed)
                self.warning_messages.add(warning_msg.id)  # Protect from deletion
                
                # Schedule warning deletion and cleanup
                def cleanup_warning():
                    asyncio.create_task(self._cleanup_warning_message(warning_msg))
                
                asyncio.get_event_loop().call_later(15, cleanup_warning)
                
            except (discord.Forbidden, discord.HTTPException):
                pass  # Can't send message, continue
            
            # Take action based on warnings
            if warnings >= self.max_warnings:
                # Reset warnings before timeout to prevent duplicates
                self.user_warnings[user_id] = 0
                # Schedule timeout without blocking
                asyncio.create_task(self.timeout_user(message.author, message.guild, 3600, "Excessive invite link spam"))
                
        except Exception as e:
            print(f"❌ Error handling invite violation: {e}")

    async def safe_delete_message(self, message):
        """Safely delete a message without causing errors"""
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            # Message already deleted or no permissions
            pass

    async def _cleanup_warning_message(self, warning_msg):
        """Clean up warning message and remove from protection list"""
        try:
            # Remove from protected messages
            self.warning_messages.discard(warning_msg.id)
            # Delete the warning message
            await warning_msg.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            # Message already deleted or no permissions
            pass

    async def timeout_user(self, member, guild, duration, reason):
        """Timeout a user (non-blocking)"""
        try:
            # Calculate timeout duration (Discord.py 2.0+ uses timedelta directly)
            timeout_until = discord.utils.utcnow() + timedelta(seconds=duration)
            await member.edit(timed_out_until=timeout_until, reason=reason)
            
            # Send timeout notification without blocking
            embed = discord.Embed(
                title="⏰ User Timed Out",
                description=f"{member.mention} has been timed out",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Duration", value=f"{duration // 60} minutes", inline=True)
            embed.add_field(name="Reason", value=reason, inline=True)
            
            # Try to find a moderation log channel (non-blocking)
            try:
                mod_channel = discord.utils.get(guild.channels, name="mod-logs") or discord.utils.get(guild.channels, name="moderation")
                if mod_channel and mod_channel.permissions_for(guild.me).send_messages:
                    await mod_channel.send(embed=embed)
                else:
                    # Send notification to the first available channel
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            timeout_msg = await channel.send(embed=embed)
                            # Schedule deletion without blocking
                            asyncio.get_event_loop().call_later(30, 
                                lambda: asyncio.create_task(self.safe_delete_message(timeout_msg)))
                            break
            except (discord.Forbidden, discord.HTTPException):
                pass  # Can't send notification, timeout was still applied
                        
        except discord.Forbidden:
            print(f"❌ Missing permissions to timeout users in {guild.name}")
        except Exception as e:
            print(f"❌ Error timing out user {member.name}: {e}")

    # Slash commands for moderation
    @app_commands.command(name="clear", description="Clear messages from the channel")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    async def clear_messages(self, interaction: discord.Interaction, amount: int):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission to use this command.", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        try:
            deleted = await interaction.channel.purge(limit=amount)
            await interaction.response.send_message(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to delete messages.", ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout a user")
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration in minutes",
        reason="Reason for timeout"
    )
    async def timeout_command(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You need 'Moderate Members' permission to use this command.", ephemeral=True)
            return
        
        if duration < 1 or duration > 40320:  # Discord max is 28 days
            await interaction.response.send_message("❌ Duration must be between 1 minute and 28 days (40320 minutes).", ephemeral=True)
            return
        
        try:
            # Use the improved timeout function
            timeout_until = discord.utils.utcnow() + timedelta(minutes=duration)
            await member.edit(timed_out_until=timeout_until, reason=reason)
            await interaction.response.send_message(f"✅ {member.mention} has been timed out for {duration} minutes.\nReason: {reason}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout users.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error timing out user: {str(e)}", ephemeral=True)

    @app_commands.command(name="modconfig", description="Configure moderation settings")
    @app_commands.describe(
        spam_threshold="Number of messages before spam detection (default: 5)",
        spam_timeframe="Timeframe in seconds for spam detection (default: 10)"
    )
    async def mod_config(self, interaction: discord.Interaction, spam_threshold: int = None, spam_timeframe: int = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to configure moderation.", ephemeral=True)
            return
        
        if spam_threshold:
            self.spam_threshold = max(3, min(20, spam_threshold))
        if spam_timeframe:
            self.spam_timeframe = max(5, min(60, spam_timeframe))
        
        embed = discord.Embed(
            title="🔧 Moderation Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="Spam Threshold", value=f"{self.spam_threshold} messages", inline=True)
        embed.add_field(name="Spam Timeframe", value=f"{self.spam_timeframe} seconds", inline=True)
        embed.add_field(name="Max Warnings", value=f"{self.max_warnings}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
    print("✅ Moderation cog loaded with anti-spam, NSFW, and invite link protection")
