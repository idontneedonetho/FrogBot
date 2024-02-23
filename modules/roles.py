# modules.roles

from modules.utils.database import db_access_with_retry, update_user_roles
from modules.utils.progression import role_thresholds
import disnake

CHANNEL_ID = 1178764276157141093

async def get_guild(client):
    guild = client.guilds[0] if client.guilds else None
    if guild is None:
        print("Guild not found. Make sure the bot is in the guild.")
        return None
    if not guild.chunked:
        await guild.chunk(cache=True)
    return guild

async def get_notification_channel(guild):
    notification_channel = guild.get_channel(CHANNEL_ID)
    if notification_channel is None:
        print("Notification channel not found. Make sure the channel ID is correct.")
    return notification_channel

async def manage_roles(member, appropriate_role, is_upgrade, notification_channel):
    roles_to_add = [appropriate_role] if appropriate_role and appropriate_role not in member.roles else []
    roles_to_remove = [role for role in member.roles if role.id in role_thresholds.values() and role != appropriate_role]
    if roles_to_add or roles_to_remove:
        await member.add_roles(*roles_to_add, reason="Updating roles based on points")
        await member.remove_roles(*roles_to_remove, reason="Removing outdated roles based on points")
        if is_upgrade and roles_to_add and notification_channel:
            await notification_channel.send(f"Congratulations! {member.mention} has been granted the following role: {appropriate_role.name}!")
    update_user_roles(member.id, member.roles)

async def get_user_roles(client, user_id):
    role_ids = db_access_with_retry('SELECT role_id FROM user_roles WHERE user_id = ?', (user_id,))
    guild = await get_guild(client)
    return [guild.get_role(role_id) for role_id in role_ids]

async def check_user_points(client):
    user_points_data = db_access_with_retry('SELECT user_id, points FROM user_points')
    guild = await get_guild(client)
    if guild is None:
        return
    notification_channel = await get_notification_channel(guild)
    for user_id, points in user_points_data:
        member = guild.get_member(user_id)
        if member is None:
            print(f"Member with ID {user_id} not found in guild.")
            member_roles = await get_user_roles(client, user_id)
            member.roles = member_roles
            continue
        appropriate_role = next((guild.get_role(role_id) for threshold, role_id in sorted(role_thresholds.items(), reverse=True) if points >= threshold), None)
        highest_existing_role = max(member.roles, key=lambda r: r.position, default=None)
        is_upgrade = highest_existing_role is None or (appropriate_role and appropriate_role.position > highest_existing_role.position)
        try:
            await manage_roles(member, appropriate_role, is_upgrade, notification_channel)
        except disnake.Forbidden:
            print(f"Bot doesn't have permission to manage roles for {member}")
        except disnake.HTTPException as e:
            print(f"HTTP request failed: {e}")