# commands/points.py

import discord
from discord.ext import commands
from .roles import check_user_points
import sqlite3
import asyncio
print('Points.py loaded')

DATABASE_FILE = 'user_points.db'

def initialize_points_database(bot, user):
    user_points = {}
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER)''')
        rows = conn.execute('SELECT * FROM user_points').fetchall()
        user_points = {user_id: points or 0 for user_id, points in rows}

        if user.id not in user_points:
            user_points[user.id] = 0
            conn.execute('INSERT INTO user_points (user_id, points) VALUES (?, ?)', (user.id, 0))

    return user_points

async def update_points(user_id, points, bot):
    with sqlite3.connect(DATABASE_FILE) as conn:
        conn.execute('UPDATE user_points SET points = ? WHERE user_id = ?', (points, user_id))
        
    await check_user_points(bot)

def get_user_points(user_id, user_points):
    return user_points.get(user_id, 0)

def is_admin():
    async def predicate(ctx):
        return ctx.message.author.guild_permissions.administrator
    return commands.check(predicate)

def setup(bot):
    bot.add_command(add_points_command)
    bot.add_command(remove_points_command)
    bot.add_command(check_or_rank_command) 

async def send_points_message(ctx, user, points_change, current_points):
    await ctx.send(f"{points_change} points {'added' if points_change >= 0 else 'removed'} from {user.mention}. "
                   f"They now have {current_points} points.")

@commands.command(name="add")
@commands.check(is_admin())
async def add_points_command(ctx, points_to_add: int, keyword: commands.clean_content, user: discord.User):
    if keyword.lower() == "points":
        user_points = initialize_points_database(ctx.bot, user)

        user_id = user.id
        current_points = get_user_points(user_id, user_points)
        new_points = current_points + points_to_add

        await update_points(user_id, new_points, ctx.bot)
        await send_points_message(ctx, user, points_to_add, new_points)
    else:
        await ctx.send("Invalid syntax. Please use '@bot add <points> points @user'.")

@commands.command(name="remove")
@commands.check(is_admin())
async def remove_points_command(ctx, points_to_remove: int, keyword: commands.clean_content, user: discord.User):
    if keyword.lower() == "points":
        user_points = initialize_points_database(ctx.bot, user)

        user_id = user.id
        current_points = get_user_points(user_id, user_points)
        new_points = current_points - points_to_remove

        await update_points(user_id, new_points, ctx.bot)
        await send_points_message(ctx, user, -points_to_remove, new_points)
    else:
        await ctx.send("Invalid syntax. Please use '@bot remove <points> points @user'.")

@commands.command(name="check")
async def check_or_rank_command(ctx, *args):
    if args and args[0].lower() == 'points':
        user = ctx.author
        if len(args) > 1:
            if args[1].lower() == 'points':
                user_id = ctx.author.id
            elif ctx.message.author.guild_permissions.administrator:
                try:
                    user = await commands.UserConverter().convert(ctx, args[1])
                    user_id = user.id
                except commands.UserNotFound:
                    await ctx.send("User not found.")
                    return
            else:
                await ctx.send("You don't have the necessary permissions to check other users' points.")
                return
        else:
            user_id = ctx.author.id

        user_points = initialize_points_database(ctx.bot, user)
        current_points = user_points.get(user_id, 0)
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)

        leaderboard_str = f">>> __**User: {user.display_name} with {current_points} points.**__\n"
        for index, (user_id, points) in enumerate(sorted_users):
            try:
                user = await ctx.guild.fetch_member(user_id)
                display_name = user.display_name
            except:
                display_name = f"User ID {user_id}"

            leaderboard_str += f"{index + 1}. {display_name}: {points} points\n"

        await ctx.send(leaderboard_str)
    else:
        await ctx.send("Invalid syntax. Please use '@bot check points @user'.")
