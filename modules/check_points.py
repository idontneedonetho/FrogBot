# check_points.py
from modules.utils.database import initialize_points_database
from modules.utils.rank_thresholds import role_thresholds, get_next_threshold
from modules.utils.progression import create_progress_bar
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

def setup(client):
    client.add_command(check_or_rank_command)