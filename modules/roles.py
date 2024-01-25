# commands/roles_module.py
import discord
from modules.utils.database import db_access_with_retry
from modules.utils.rank_thresholds import role_thresholds
import asyncio

CHANNEL_ID = 1178764276157141093
cmd = {}

async def check_user_points(client):
    user_points_data = db_access_with_retry('SELECT user_id, points FROM user_points')
    print("Checking user points...")
    guild = client.guilds[0] if client.guilds else None
    if guild is None:
        print("Guild not found. Make sure the bot is in the guild.")
        return

    try:
        if not guild.chunked:
            await guild.chunk(cache=True)
    except Exception as e:
        print(f"Failed to chunk guild: {e}")
        return

    notification_channel = guild.get_channel(CHANNEL_ID)
    if notification_channel is None:
        print("Notification channel not found. Make sure the channel ID is correct.")
        return
    else:
        pass
    
    for user_id, points in user_points_data:
        member = guild.get_member(user_id)
        if member is None:
            print(f"Member with ID {user_id} not found in guild.")
            continue

        appropriate_role = None
        for threshold, role_id in sorted(role_thresholds.items(), reverse=True):
            if points >= threshold:
                appropriate_role = guild.get_role(role_id)
                break

        roles_to_remove = [role for role in member.roles if role.id in role_thresholds.values()]

        if points < min(role_thresholds.keys()):
            print(f"User points ({points}) are below the lowest threshold. Removing roles: {roles_to_remove}")
        elif appropriate_role and appropriate_role not in member.roles:
            print(f"Updating roles for {member.name}...")
            roles_to_add = [appropriate_role]
            roles_to_remove = [role for role in roles_to_remove if role != appropriate_role]
            print(f"Adding role: {appropriate_role}, Removing roles: {roles_to_remove}")
        else:
            continue

        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Removing outdated roles based on points")
            if 'roles_to_add' in locals() and roles_to_add:
                await member.add_roles(*roles_to_add, reason="Updating roles based on points")
                await notification_channel.send(f"Congratulations! {member.mention} has been granted the following role: {appropriate_role.name}!")
        except discord.Forbidden:
            print(f"Bot doesn't have permission to manage roles for {member}")
        except discord.HTTPException as e:
            print(f"HTTP request failed: {e}")
