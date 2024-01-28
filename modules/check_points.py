# check_points.py
from modules.utils.database import initialize_points_database
from modules.utils.progression import create_progress_bar, calculate_user_rank_and_next_rank_name, role_thresholds
from discord.ext import commands
import discord
import datetime

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
        user_points = initialize_points_database(user)
        sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
        user_rank = next((index for index, (u_id, _) in enumerate(sorted_users) if u_id == user.id), -1)
        start_index = max(0, user_rank - 2)
        if start_index < 2:
            end_index = min(5, len(sorted_users))
        else:
            end_index = min(start_index + 5, len(sorted_users))
        end_index = min(len(sorted_users), start_index + 5)
        if not ctx.guild:
            await ctx.send("This command can only be used in a guild.")
            return
        embed = discord.Embed(
            title="**🏆 Your Current Standing**",
            description="Here's your current points, rank, etc.",
            color=discord.Color.gold()
        )
        for index in range(start_index, end_index):
            user_id, points = sorted_users[index]
            member = ctx.guild.get_member(user_id)
            if member is None:
                continue
            display_name = member.display_name
            _, next_rank_name, points_needed, current_threshold, next_threshold = calculate_user_rank_and_next_rank_name(ctx, member, role_thresholds)
            progress_length = next_threshold - current_threshold
            progress_current = points - current_threshold
            progress_bar = create_progress_bar(progress_current, progress_length)
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

def setup(client):
    client.add_command(check_or_rank_command)