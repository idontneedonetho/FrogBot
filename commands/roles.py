# commands/roles.py

import discord
import sqlite3
import asyncio
print('Roles.py loaded')

async def check_user_points(bot):
    role_thresholds = {
        1000: 1173370706759786549,
        2500: 1183575706018521189,
        5000: 1178751322506416138,
        10000: 1178751607509364828,
        25000: 1178751819434963044,
        50000: 1178751897855856790,
        100000: 1178751985760079995,
        250000: 1178752169894223983,
        500000: 1178752236717883534,
        1000000: 1178752300592922634
    }

    # Connect to SQLite database
    connection = sqlite3.connect('user_points.db')
    cursor = connection.cursor()

    # Get the Discord guild object
    guild = bot.get_guild(698205243103641711)

    # Loop through each user in the database
    for row in cursor.execute('SELECT user_id, points FROM user_points'):
        # Get the Discord member object
        member = guild.get_member(row[0])

        if member is None:
            continue

        # Remove all roles related to points system
        roles_to_remove = [guild.get_role(role_id) for role_id in role_thresholds.values() if guild.get_role(role_id)]
        await member.remove_roles(*roles_to_remove)

        # Add role based on points
        for threshold, role_id in sorted(role_thresholds.items(), reverse=True):
            if row[1] >= threshold:
                role_to_add = guild.get_role(role_id)
                if role_to_add:
                    await member.add_roles(role_to_add)
                    break

    # Close the database connection
    connection.close()
