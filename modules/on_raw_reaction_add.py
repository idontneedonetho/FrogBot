# commands/raw_reaction_add_handler.py
from modules.utils.database import initialize_points_database
from modules.emoji import process_reaction
from modules.roles import check_user_points

async def on_raw_reaction_add(payload):
    bot = payload.member.guild   # Access the bot instance from the payload
    
    if payload.member and payload.member.guild_permissions.administrator:
        user = payload.member
        user_points = initialize_points_database(user)
        channel = bot.get_channel(payload.channel_id)
        await process_reaction(bot, payload, user_points)
        await check_user_points(bot)
    else:
        print(f"{payload.member.display_name} does not have the Administrator permission. Ignoring the reaction.")

def setup(bot):
    bot.add_listener(on_raw_reaction_add, 'on_raw_reaction_add')