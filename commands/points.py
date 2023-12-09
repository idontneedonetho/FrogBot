# commands/points.py
import discord
from discord.ext import commands
import sqlite3
from .events import points_updated

def initialize_points_database():
    conn = sqlite3.connect('user_points.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER)''')
    user_points = {user_id: points or 0 for user_id, points in c.execute('SELECT * FROM user_points')}
    return user_points

def is_admin():
    async def predicate(ctx):
        return ctx.message.author.guild_permissions.administrator
    return commands.check(predicate)

def setup(bot):
    bot.add_command(add_points_command)
    bot.add_command(remove_points_command)
    bot.add_command(check_points_command)
    bot.add_command(my_rank_command)

@commands.command(name="add")
@commands.check(is_admin())
async def add_points_command(ctx, points_to_add: int, keyword: commands.clean_content, user: discord.User):
    if ctx.message.author.guild_permissions.administrator:
        if keyword.lower() == "points":
            user_points = initialize_points_database()

            user_id = user.id
            current_points = user_points.get(user_id, 0)
            new_points = current_points + points_to_add

            conn = sqlite3.connect('user_points.db')
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (user_id, new_points))
            conn.commit()
            conn.close()
            
            await update_points(user_id, new_points)

            await ctx.send(f"{points_to_add} points added to {user.mention}. They now have {new_points} points.")
        else:
            await ctx.send("Invalid syntax. Please use '@bot add <points> points @user'.")
    else:
        await ctx.send("You do not have the necessary permissions to add points.")

@commands.command(name="remove")
@commands.check(is_admin())
async def remove_points_command(ctx, points_to_remove: int, keyword: commands.clean_content, user: discord.User):
    if ctx.message.author.guild_permissions.administrator:
        if keyword.lower() == "points":
            user_points = initialize_points_database()

            user_id = user.id
            current_points = user_points.get(user_id, 0)
            new_points = current_points - points_to_remove

            conn = sqlite3.connect('user_points.db')
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (user_id, new_points))
            conn.commit()
            conn.close()
            
            await update_points(user_id, new_points)

            await ctx.send(f"{points_to_remove} points removed from {user.mention}. They now have {new_points} points.")
        else:
            await ctx.send("Invalid syntax. Please use '@bot remove <points> points @user'.")
    else:
        await ctx.send("You do not have the necessary permissions to remove points.")

@commands.command(name="check")
@commands.check(is_admin())
async def check_points_command(ctx, *args):
    if ctx.message.author.guild_permissions.administrator:
        if args and args[0].lower() == 'points':
            user = ctx.author
            if len(args) > 1:
                try:
                    user = await commands.UserConverter().convert(ctx, args[1])
                except commands.UserNotFound:
                    await ctx.send("User not found.")
                    return

            user_points = initialize_points_database()

            user_id = user.id
            current_points = user_points.get(user_id, 0)

            await ctx.send(f"{user.mention} has {current_points} points.")
        else:
            await ctx.send("Invalid syntax. Please use '@bot check points @user'.")
    else:
        await ctx.send("You do not have the necessary permissions to check other users points.")

@commands.command(name="my")
async def my_rank_command(ctx, keyword: commands.clean_content):
    if keyword.lower() == "rank":
        user_points = initialize_points_database()
        user_id = ctx.author.id
        current_points = user_points.get(user_id, 0)
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        user_index = next((index for index, (id, points) in enumerate(sorted_users) if id == user_id), None)

        if user_index is not None:
            start_index = max(0, user_index - 2)
            end_index = min(len(sorted_users) - 1, user_index + 1)
            leaderboard_str = f">>> Your rank: **#{user_index + 1}** with {current_points} points.\n\n"
            for index in range(start_index, end_index + 1):
                user_id, points = sorted_users[index]

                try:
                    user = await ctx.guild.fetch_member(user_id)
                    display_name = user.display_name
                except:
                    display_name = f"User ID {user_id}"

                if user_id == ctx.author.id:
                    leaderboard_str += f"**{index + 1}. {display_name}: {points} points**\n"
                else:
                    leaderboard_str += f"{index + 1}. {display_name}: {points} points\n"

            await ctx.send(leaderboard_str)
        else:
            await ctx.send("You have not earned any points yet.")
    else:
        await ctx.send("Invalid syntax. Please use '@bot my rank'.")

async def update_points(user_id, new_points):
    conn = sqlite3.connect('user_points.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (user_id, new_points))
    conn.commit()
    conn.close()

    # Emit the points_updated event with both user_id and new_points
    await points_updated.emit(user_id, new_points)