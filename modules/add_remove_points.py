# add_remove_points.py
from modules.utils.database import initialize_points_database, update_points, get_user_points
from modules.utils.rank_thresholds import role_thresholds
from modules.utils.progression import calculate_user_rank_and_next_rank_name, create_points_embed
from modules.roles import check_user_points
from discord.ext import commands
import discord

def is_admin():
    async def predicate(ctx):
        author = ctx.message.author
        is_admin = author.guild_permissions.administrator
        print(f"Checking admin status for {author} (ID: {author.id}): {is_admin}")
        return is_admin
    return commands.check(predicate)

@commands.command(name="add")
@is_admin()
async def add_points_command(ctx, points_to_add: int, keyword: str, user: discord.User):
    keyword = await commands.clean_content().convert(ctx, keyword)
    if keyword:
        action = "add"
        user_points = initialize_points_database(user)
        user_id = user.id
        current_points = get_user_points(user_id, user_points)
        new_points = current_points + points_to_add
        if await update_points(user_id, new_points):
            await check_user_points(ctx.bot)
        user_rank, next_rank_name = calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
        new_embed = create_points_embed(user, new_points, role_thresholds, action, user_rank, next_rank_name)
        await ctx.reply(embed=new_embed)
    else:
        await ctx.reply("Invalid syntax. Please use '@bot add <points> point/points @user'.")

@commands.command(name="remove")
@is_admin()
async def remove_points_command(ctx, points_to_remove: int, keyword: str, user: discord.User):
    keyword = await commands.clean_content().convert(ctx, keyword)
    if keyword:
        action = "remove"
        user_points = initialize_points_database(user)
        user_id = user.id
        current_points = get_user_points(user_id, user_points)
        new_points = max(current_points - points_to_remove, 0)
        if await update_points(user_id, new_points):
            await check_user_points(ctx.bot)
        user_rank, next_rank_name = calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
        new_embed = create_points_embed(user, new_points, role_thresholds, action, user_rank, next_rank_name)
        await ctx.reply(embed=new_embed)
    else:
        await ctx.reply("Invalid syntax. Please use '@bot remove <points> point/points @user'.")

def setup(client):
    client.add_command(add_points_command)
    client.add_command(remove_points_command)
