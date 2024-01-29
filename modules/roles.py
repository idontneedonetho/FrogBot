# commands/roles_module.py
import discord
from modules.utils.database import db_access_with_retry
from modules.utils.progression import role_thresholds

CHANNEL_ID = 1178764276157141093

async def check_user_points(client):
    user_points_data = db_access_with_retry('SELECT user_id, points FROM user_points')
    guild = client.guilds[0] if client.guilds else None
    if guild is None:
        print("Guild not found. Make sure the bot is in the guild.")
        return

    if not guild.chunked:
        await guild.chunk(cache=True)

    notification_channel = guild.get_channel(CHANNEL_ID)
    if notification_channel is None:
        print("Notification channel not found. Make sure the channel ID is correct.")
        return

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

        if appropriate_role is None:
            roles_to_remove = [role for role in member.roles if role.id in role_thresholds.values()]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="Removing all roles due to insufficient points")
        elif appropriate_role not in member.roles:
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