#!/usr/bin/env python3
"""
Generate a proper Discord bot invite link with slash command support
"""
import discord
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get bot ID from environment or use the one from the logs
BOT_ID = "1392013847560327240"  # From your bot logs

def generate_invite_url():
    """Generate invite URL with proper permissions and scopes"""
    
    # Required permissions for your bot
    permissions = discord.Permissions(
        # Core permissions
        read_messages=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_external_emojis=True,
        
        # Server management permissions
        manage_channels=True,
        manage_roles=True,
        
        # Member permissions
        kick_members=True,  # Optional
        ban_members=True,   # Optional
        
        # Voice permissions (for stats channels)
        connect=True,
        
        # Admin (you can remove this and use specific permissions instead)
        administrator=True
    )
    
    # Generate URL with BOTH required scopes
    invite_url = discord.utils.oauth_url(
        BOT_ID,
        permissions=permissions,
        scopes=["bot", "applications.commands"]  # THIS IS THE KEY PART!
    )
    
    return invite_url

if __name__ == "__main__":
    invite_url = generate_invite_url()
    
    print("=" * 80)
    print("🔗 DISCORD BOT INVITE LINK")
    print("=" * 80)
    print()
    print("Copy this URL and paste it in your browser:")
    print()
    print(invite_url)
    print()
    print("⚠️  IMPORTANT STEPS:")
    print("1. Click the link above")
    print("2. Select your server")
    print("3. Make sure BOTH checkboxes are selected:")
    print("   ✅ bot")
    print("   ✅ applications.commands")
    print("4. Select the permissions you want")
    print("5. Click 'Authorize'")
    print()
    print("🔄 If your bot is already in the server:")
    print("1. Kick the bot from your server first")
    print("2. Then use this new invite link")
    print("3. The bot profile should then show 'Supports slash commands'")
    print()
    print("=" * 80)
