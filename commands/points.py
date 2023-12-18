# commands/points.py

import discord
from discord.ext import commands
from .roles import check_user_points
from .leaderboard import update_leaderboard
import random
import datetime
import sqlite3
import time
import asyncio

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
    #await update_leaderboard(bot)

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

def create_points_embed(user, current_points, role_thresholds, action):
    title = "Points Added ⬆️" if action == "add" else "Points Removed ⬇️"
    next_role_id = next((threshold_role_id for threshold, threshold_role_id in sorted(role_thresholds.items()) if current_points < threshold), None)
    next_rank_name = "Max Rank" if next_role_id is None else "Next Rank"
    points_needed = get_next_threshold(current_points, role_thresholds) - current_points
    progress_bar = create_progress_bar(current_points, get_next_threshold(current_points, role_thresholds))

    embed = discord.Embed(
        title=title,
        description=f"Here's the current standing of {user.display_name}.",
        color=discord.Color.green()
    )

    rank_emoji = "🌟"
    rank_text = f"{rank_emoji} **{user.display_name}: {current_points} points**\nProgress: {progress_bar} ({points_needed} pts to {next_rank_name})"
    embed.add_field(name="\u200b", value=rank_text, inline=False)

    return embed

@commands.command(name="add")
@is_admin()
async def add_points_command(ctx, points_to_add: int, keyword: commands.clean_content, user: discord.User):
    if keyword.lower() == "points":
        user_points = initialize_points_database(ctx.bot, user)

        user_id = user.id
        current_points = get_user_points(user_id, user_points)
        new_points = current_points + points_to_add

        await update_points(user_id, new_points, ctx.bot)
        new_embed = create_points_embed(user, new_points, role_thresholds, action="add")
        await ctx.reply(embed=new_embed)
    else:
        await ctx.reply("Invalid syntax. Please use '@bot add <points> points @user'.")

@commands.command(name="remove")
@is_admin()
async def remove_points_command(ctx, points_to_remove: int, keyword: commands.clean_content, user: discord.User):
    if keyword.lower() == "points":
        user_points = initialize_points_database(ctx.bot, user)

        user_id = user.id
        current_points = get_user_points(user_id, user_points)
        new_points = current_points - points_to_remove

        await update_points(user_id, new_points, ctx.bot)
        new_embed = create_points_embed(user, new_points, role_thresholds, action="remove")
        await ctx.reply(embed=new_embed)
    else:
        await ctx.reply("Invalid syntax. Please use '@bot remove <points> points @user'.")

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

def get_next_threshold(points, thresholds):
    for threshold in sorted(thresholds.keys()):
        if points < threshold:
            return threshold
    return max(thresholds.keys())

def create_progress_bar(current, total, length=10):
    if total == 0:
        total = 1
    progress = int((current / total) * length)
    return '█' * progress + '░' * (length - progress)

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

        if not ctx.guild:
            await ctx.send("This command can only be used in a guild.")
            return

        role_id_to_name = {role.id: role.name for role in ctx.guild.roles}

        embed = discord.Embed(
            title="**🏆 Your Current Standing**",
            description="Here's your current points, rank, etc.",
            color=discord.Color.gold()
        )

        for index in range(start_index, end_index):
            user_id, points = sorted_users[index]

            try:
                member = await ctx.guild.fetch_member(user_id)
                display_name = member.display_name
            except Exception:
                display_name = f"User ID {user_id}"

            next_role_id = next((threshold_role_id for threshold, threshold_role_id in sorted(role_thresholds.items()) if points < threshold), None)
            next_rank_name = role_id_to_name.get(next_role_id, "next rank")

            points_needed = get_next_threshold(points, role_thresholds) - points
            progress_bar = create_progress_bar(points, get_next_threshold(points, role_thresholds))

            rank_text = ""
            if index < 3:
                rank_emoji = ["🥇", "🥈", "🥉"][index]
                if user_id == user.id:
                    rank_text = f"{rank_emoji} | ***__{display_name}: {points:,} points__***\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
                else:
                    rank_text = f"{rank_emoji} | {display_name}: {points:,} points\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
            else:
                if user_id == user.id:
                    rank_text = f"***__#{index + 1} | {display_name}: {points:,} points__***\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
                else:
                    rank_text = f"#{index + 1} | {display_name}: {points:,} points\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
        
            embed.add_field(name="\u200b", value=rank_text, inline=False)
            
        embed.set_footer(text=f"Leaderboard as of {datetime.datetime.now().strftime('%Y-%m-%d')}")
        await ctx.send(embed=embed)

    else:
        await ctx.send("Invalid syntax. Please use '@bot check points [@user]'.")
