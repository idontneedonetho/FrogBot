# modules.check_points

from modules.utils.progression import create_progress_bar, calculate_user_rank_and_next_rank_name, role_thresholds
from modules.utils.database import initialize_points_database
from disnake.ext import commands
from disnake import User
import datetime
import disnake

async def get_user(ctx, args):
    if len(args) > 1 and ctx.message.author.guild_permissions.administrator:
        try:
            return await commands.UserConverter().convert(ctx, args[1])
        except commands.UserNotFound:
            await ctx.send("User not found.")
            return None
    else:
        return ctx.author

@commands.slash_command(description="Check points")
async def check_points(ctx, user: User = None):
    if user is None or ctx.author == user or ctx.author.guild_permissions.administrator:
        if user is None:
            user = ctx.author
        user_points = initialize_points_database(user)
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        user_rank = next((index for index, (u_id, _) in enumerate(sorted_users) if u_id == user.id), -1)
        start_index = max(0, user_rank - 2)
        end_index = min(len(sorted_users), start_index + 5) if start_index < 2 else min(start_index + 5, len(sorted_users))
        if not ctx.guild:
            await ctx.send("This command can only be used in a guild.")
            return
        embed = disnake.Embed(
            title="**🏆 Your Current Standing**",
            description="Here's your current points, rank, etc.",
            color=disnake.Color.gold()
        )
        embed_fields = [
            create_embed_field(ctx, user, sorted_users, index)
            for index in range(start_index, end_index)
        ]
        for field in embed_fields:
            if field is not None:
                embed.add_field(name="\u200b", value=field, inline=False)
        embed.set_footer(text=f"Leaderboard as of {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
        await ctx.send(embed=embed)
    else:
        await ctx.send("Invalid syntax. Please use '/check points [@user]'.")

def create_embed_field(ctx, user, sorted_users, index):
    user_id, points = sorted_users[index]
    member = ctx.guild.get_member(user_id)
    if member is None:
        return None
    display_name = member.display_name
    _, next_rank_name, points_needed, current_threshold, next_threshold = calculate_user_rank_and_next_rank_name(ctx, member, role_thresholds)
    progress_length = next_threshold - current_threshold
    progress_current = points - current_threshold
    progress_bar = create_progress_bar(progress_current, progress_length)
    rank_text = ""
    if index < 3:
        rank_emoji = ["🥇", "🥈", "🥉"][index]
    else:
        rank_emoji = f"#{index + 1}"
    rank_text = f"{rank_emoji} | {'***__' if user_id == user.id else ''}{display_name}: {points:,} points{'__***' if user_id == user.id else ''}\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
    return rank_text

def setup(client):
    client.add_slash_command(check_points)