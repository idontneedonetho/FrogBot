# commands/raw_reaction_add_handler.py
from modules.utils.database import initialize_points_database
from modules.roles import check_user_points
cmd = {}  # No specific commands for this module

async def on_raw_reaction_add(client, payload):
    user_id = payload.user_id
    guild_id = payload.guild_id
    guild = client.get_guild(guild_id)
    member = guild.get_member(user_id)
    if member and member.guild_permissions.administrator:
        user = client.get_user(user_id)
        user_points = initialize_points_database(client, user)
        channel = client.get_channel(payload.channel_id)
        await emoji.process_reaction(client, payload, user_points)
        await check_user_points(client)
    else:
        user = await client.fetch_user(user_id)
        user_name = user.name
        print(f"{user_name} does not have the Administrator permission. Ignoring the reaction.")