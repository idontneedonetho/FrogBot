# commands/points.py

import discord
from discord.ext import commands
from .roles import check_user_points
from .leaderboard import update_leaderboard
import sqlite3
import time
import asyncio
print('Points.py loaded')

DATABASE_FILE = 'user_points.db'

def db_access_with_retry(sql_operation, *args, max_attempts=5, delay=1, timeout=10.0):
    for attempt in range(max_attempts):
        try:
            with sqlite3.connect(DATABASE_FILE, timeout=timeout) as conn:
                cursor = conn.cursor()
                cursor.execute(sql_operation, args)
                if sql_operation.strip().upper().startswith('SELECT'):
                    results = cursor.fetchall()
                    cursor.close()
                    return results
                conn.commit()
                cursor.close()
                return
        except sqlite3.OperationalError as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)

def initialize_points_database(bot, user):
    user_points = {}

    rows = db_access_with_retry('SELECT * FROM user_points')
    user_points = {user_id: points or 0 for user_id, points in rows}

    if user.id not in user_points:
        user_points[user.id] = 0
        db_access_with_retry('INSERT INTO user_points (user_id, points) VALUES (?, ?)', user.id, 0)

    return user_points

async def update_points(user_id, points, bot):
    db_access_with_retry('UPDATE user_points SET points = ? WHERE user_id = ?', points, user_id)
    await check_user_points(bot)
    await update_leaderboard(bot)

def get_user_points(user_id, user_points):
    return user_points.get(user_id, 0)

def is_admin():
    async def predicate(ctx):
        author = ctx.message.author
        is_admin = author.guild_permissions.administrator
        print(f"Checking admin status for {author} (ID: {author.id}): {is_admin}")
        return is_admin
    return commands.check(predicate)

def setup(bot):
    bot.add_command(add_points_command)
    bot.add_command(remove_points_command)
    bot.add_command(check_or_rank_command) 

async def send_points_message(ctx, user, points_change, current_points):
    await ctx.send(f"{points_change} points {'added' if points_change >= 0 else 'removed'} from {user.mention}. "
                   f"They now have {current_points} points.")

@commands.command(name="add")
@is_admin()
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
@is_admin()
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
            if ctx.message.author.guild_permissions.administrator:
                try:
                    user = await commands.UserConverter().convert(ctx, args[1])
                except commands.UserNotFound:
                    await ctx.send("User not found.")
                    return
            else:
                await ctx.send("You don't have the necessary permissions to check other users' points.")
                return

        user_points = initialize_points_database(ctx.bot, user)
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)

        user_rank = next((index for index, (u_id, _) in enumerate(sorted_users) if u_id == user.id), -1)
        
        start_index = max(0, min(user_rank - 2, len(sorted_users) - 5))
        end_index = min(len(sorted_users), start_index + 5)

        embed = discord.Embed(title="__Leaderboard__", color=discord.Color.blue())
        for index in range(start_index, end_index):
            user_id, points = sorted_users[index]
            try:
                member = await ctx.guild.fetch_member(user_id)
                display_name = member.display_name
            except:
                display_name = f"User ID {user_id}"

            rank_text = f"{display_name}: {points} points"
            if user_id == user.id:
                rank_text = f"***{rank_text}***"

            embed.add_field(name=f"#{index + 1}", value=rank_text, inline=False)

        await ctx.send(embed=embed)
    else:
        await ctx.send("Invalid syntax. Please use '@bot check points [@user]'.")
