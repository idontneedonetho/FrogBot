# add_remove_points.py
from modules.utils.database import initialize_points_database, update_points, get_user_points
from modules.utils.progression import calculate_user_rank_and_next_rank_name, create_points_embed, role_thresholds
from modules.utils.commons import is_admin
from modules.roles import check_user_points
from discord.ext import commands
import re

@commands.command(name="add")
@is_admin()
async def add_points_command(ctx, points_to_add: int, keyword: str, mention: str):
    keyword = await commands.clean_content().convert(ctx, keyword)
    if keyword:
        user_id_match = re.match(r'<@!?(\d+)>', mention)
        if not user_id_match:
            await ctx.reply("Invalid user mention.")
            return
        user_id = int(user_id_match.group(1))
        user = ctx.guild.get_member(user_id)
        if not user:
            await ctx.reply("User not found.")
            return
        print(f"Adding points: Keyword: {keyword}, Points: {points_to_add}, User: {user}")
        if points_to_add < 0:
            print("Invalid points.")
            await ctx.reply("Points must be a positive number.")
            return
        action = "add"
        user_points = initialize_points_database(user)
        current_points = get_user_points(user_id, user_points)
        new_points = current_points + points_to_add
        if await update_points(user_id, new_points):
            await check_user_points(ctx.bot)
        user_rank, next_rank_name, _, _, _ = calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
        new_embed = create_points_embed(ctx, user, new_points, role_thresholds, action, user_rank, next_rank_name)
        await ctx.reply(embed=new_embed)
    else:
        print("Invalid syntax.")
        await ctx.reply("Invalid syntax. Please use '@bot add <points> point/points @user'.")

@commands.command(name="remove")
@is_admin()
async def remove_points_command(ctx, points_to_remove: int, keyword: str, mention: str):
    keyword = await commands.clean_content().convert(ctx, keyword)
    if keyword:
        user_id_match = re.match(r'<@!?(\d+)>', mention)
        if not user_id_match:
            await ctx.reply("Invalid user mention.")
            return
        user_id = int(user_id_match.group(1))
        user = ctx.guild.get_member(user_id)
        if not user:
            await ctx.reply("User not found.")
            return
        print(f"Removing points: Keyword: {keyword}, Points: {points_to_remove}, User: {user}")
        if points_to_remove < 0:
            print("Invalid points.")
            await ctx.reply("Points must be a positive number.")
            return
        action = "remove"
        user_points = initialize_points_database(user)
        current_points = get_user_points(user_id, user_points)
        new_points = max(current_points - points_to_remove, 0)
        if await update_points(user_id, new_points):
            await check_user_points(ctx.bot)
        user_rank, next_rank_name, _, _, _ = calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
        new_embed = create_points_embed(ctx, user, new_points, role_thresholds, action, user_rank, next_rank_name)
        await ctx.reply(embed=new_embed)
    else:
        print("Invalid syntax.")
        await ctx.reply("Invalid syntax. Please use '@bot remove <points> point/points @user'.")

def setup(client):
    client.add_command(add_points_command)
    client.add_command(remove_points_command)
