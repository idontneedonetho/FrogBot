# commands/points.py
import discord
from discord.ext import commands
import sqlite3

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
    bot.add_command(my_points_command)

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

            if current_points >= points_to_remove:
                new_points = current_points - points_to_remove

                conn = sqlite3.connect('user_points.db')
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (user_id, new_points))
                conn.commit()
                conn.close()

                await ctx.send(f"{points_to_remove} points removed from {user.mention}. They now have {new_points} points.")
            else:
                await ctx.send(f"{user.mention} does not have enough points to remove.")
        else:
            await ctx.send("Invalid syntax. Please use '@bot remove <points> points @user'.")
    else:
        await ctx.send("You do not have the necessary permissions to remove points.")

@commands.command(name="check")
@commands.check(is_admin())
async def check_points_command(ctx, *args):
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

@commands.command(name="my")
async def my_points_command(ctx, keyword: commands.clean_content):
    if keyword.lower() == "points":
        user_points = initialize_points_database()

        user_id = ctx.author.id
        current_points = user_points.get(user_id, 0)

        await ctx.send(f"You have {current_points} points.")
    else:
        await ctx.send("Invalid syntax. Please use '@bot my points'.")
