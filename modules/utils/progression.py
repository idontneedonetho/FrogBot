import discord
import datetime
from modules.utils.database import initialize_points_database

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

def calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds):
    user_points = initialize_points_database(user)
    current_points = user_points.get(user.id, 0)
    current_threshold = max((points for points in role_thresholds.keys() if points <= current_points), default=0)
    next_threshold = get_next_threshold(current_points, role_thresholds)
    next_role_id = next((role_id for points, role_id in sorted(role_thresholds.items()) if current_points < points), None)
    if next_role_id is not None:
        next_rank_role = ctx.guild.get_role(next_role_id)
        next_rank_name = next_rank_role.name if next_rank_role else "Next Rank"
        points_needed = next_threshold - current_points
    else:
        next_rank_name = "Max Rank"
        points_needed = 0
    sorted_users = sorted(user_points.items(), key=lambda x: x[1], reverse=True)
    user_rank = next((index for index, (u_id, _) in enumerate(sorted_users) if u_id == user.id), -1)
    return user_rank, next_rank_name, points_needed, current_threshold, next_threshold

def create_progress_bar(current, total, length=10, fill_symbols='█▉▊▋▌▍▎▏', empty=' '):
    if total == 0:
        total = 1
    progress = int(current / total * length * len(fill_symbols))
    filled_count = progress // len(fill_symbols)
    remainder_fill = progress % len(fill_symbols)
    return (fill_symbols[0] * filled_count) + (fill_symbols[remainder_fill] if remainder_fill > 0 else '') + empty * (length - filled_count - 1)

def create_points_embed(ctx, user, current_points, role_thresholds, action, user_rank, next_rank_name):
    title = "Points Added ⬆️" if action == "add" else "Points Removed ⬇️"
    user_rank, next_rank_name, points_needed, current_threshold, next_threshold = calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
    progress_length = next_threshold - current_threshold
    progress_current = current_points - current_threshold
    progress_bar = create_progress_bar(progress_current, progress_length)
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