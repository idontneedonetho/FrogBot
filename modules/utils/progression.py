# progression.py

import discord
import datetime
from modules.utils.rank_thresholds import get_next_threshold
from modules.utils.database import initialize_points_database

def calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds):
    user_points = initialize_points_database(user)
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
    user_rank = next((index for index, (u_id, _) in enumerate(sorted_users) if u_id == user.id), -1)
    next_threshold = get_next_threshold(user_points[user.id], role_thresholds)
    next_role_id = next((role_id for threshold, role_id in sorted(role_thresholds.items()) if user_points[user.id] < threshold), None)
    if next_role_id is not None:
        next_rank_role = ctx.guild.get_role(next_role_id)
        next_rank_name = next_rank_role.name if next_rank_role else "Next Rank"
    else:
        next_rank_name = "Max Rank"
    return user_rank, next_rank_name

def create_progress_bar(current, total, length=10, fill_symbols='█▉▊▋▌▍▎▏', empty=' '):
    progress = int(current / total * length * len(fill_symbols))
    filled_count = progress // len(fill_symbols)
    remainder_fill = int(progress % len(fill_symbols))
    return (fill_symbols[0] * filled_count) + fill_symbols[remainder_fill].ljust(length - filled_count, empty)

def create_points_embed(user, current_points, role_thresholds, action, user_rank, next_rank_name):
    title = "Points Added ⬆️" if action == "add" else "Points Removed ⬇️"
    points_needed = get_next_threshold(current_points, role_thresholds) - current_points
    progress_bar = create_progress_bar(current_points, get_next_threshold(current_points, role_thresholds))
    rank_emojis = ["🥇", "🥈", "🥉"]
    rank_emoji = rank_emojis[user_rank] if user_rank < 3 else f"#{user_rank + 1}"
    rank_text = f"**__{rank_emoji} | {user.display_name}: {current_points:,} points__**\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
    embed = discord.Embed(
        title=title,
        description=f"Here's the current standing of {user.display_name}.",
        color=discord.Color.green()
    )
    embed.add_field(name="\u200b", value=rank_text, inline=False)
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d')}")
    return embed