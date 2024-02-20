# modules.add_remove_points

from modules.utils.progression import calculate_user_rank_and_next_rank_name, create_points_embed, role_thresholds
from modules.utils.database import initialize_points_database, update_points, get_user_points
from modules.roles import check_user_points
from modules.utils.commons import is_admin
from disnake.ext import commands
from disnake import User

@commands.slash_command(description="Add points to a user")
@is_admin()
async def add(ctx, points: int, user: User):
    await handle_points_command(ctx, points, user, "add")

@commands.slash_command(description="Remove points from a user")
@is_admin()
async def remove(ctx, points: int, user: User):
    await handle_points_command(ctx, points, user, "remove")

async def handle_points_command(ctx, points, user, action):
    print(f"{action.capitalize()}ing points: Points: {points}, User: {user}")
    if points < 0:
        print("Invalid points.")
        await ctx.send("Points must be a positive number.")
        return
    user_points = initialize_points_database(user)
    current_points = get_user_points(user.id, user_points)
    new_points = current_points + points if action == "add" else current_points - points
    if await update_points(user.id, new_points):
        await check_user_points(ctx.bot)
    user_rank, next_rank_name, _, _, _ = calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
    new_embed = create_points_embed(ctx, user, new_points, role_thresholds, action, user_rank, next_rank_name)
    await ctx.send(embed=new_embed)

def setup(client):
    client.add_slash_command(add)
    client.add_slash_command(remove)