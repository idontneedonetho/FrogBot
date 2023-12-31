# commands/roles.py

import discord
import sqlite3
import asyncio

CHANNEL_ID = 1178764276157141093

async def check_user_points(bot):
    role_thresholds = {
        1000: 1178750004869996574,
        2500: 1178751163462586368,
        5000: 1178751322506416138,
        10000: 1178751607509364828,
        25000: 1178751819434963044,
        50000: 1178751897855856790,
        100000: 1178751985760079995,
        250000: 1178752169894223983,
        500000: 1178752236717883534,
        1000000: 1178752300592922634
    }

    connection = sqlite3.connect('user_points.db')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_points (
            user_id INTEGER PRIMARY KEY,
            points INTEGER
        )
    ''')
    connection.commit()

    guild = bot.guilds[0] if bot.guilds else None
    if guild is None:
        print("Guild not found. Make sure the guild ID is correct.")
        return

    if not guild.chunked:
        await guild.chunk(cache=True)

    notification_channel = guild.get_channel(CHANNEL_ID)
    if notification_channel is None:
        print("Notification channel not found. Make sure the channel ID is correct.")
        return
    
    for user_id, points in cursor.execute('SELECT user_id, points FROM user_points'):
        member = guild.get_member(user_id)
        if member is None:
            continue
    
        appropriate_role = None
        for threshold, role_id in sorted(role_thresholds.items(), reverse=True):
            if points >= threshold:
                appropriate_role = guild.get_role(role_id)
                break
    
        if appropriate_role and appropriate_role not in member.roles:
            try:
                highest_existing_role = max(member.roles, key=lambda r: r.position, default=None)
                is_upgrade = highest_existing_role is None or appropriate_role.position > highest_existing_role.position
    
                roles_to_add = [appropriate_role]
                roles_to_remove = [role for role in member.roles if role.id in role_thresholds.values() and role != appropriate_role]
                
                if roles_to_add or roles_to_remove:
                    await member.add_roles(*roles_to_add, reason="Updating roles based on points")
                    await member.remove_roles(*roles_to_remove, reason="Removing outdated roles based on points")
    
                    if is_upgrade:
                        await notification_channel.send(f"Congratulations! {member.mention} has been granted the following role: {appropriate_role.name}!")
    
            except discord.Forbidden:
                print(f"Bot doesn't have permission to manage roles for {member}")
            except discord.HTTPException as e:
                print(f"HTTP request failed: {e}")
    
    connection.close()
