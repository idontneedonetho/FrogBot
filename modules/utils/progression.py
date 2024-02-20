# modules.utils.progression

from modules.utils.database import initialize_points_database
from bisect import bisect_right
import datetime
import disnake

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

sorted_thresholds = sorted(role_thresholds.keys())
sorted_roles = [role_thresholds[threshold] for threshold in sorted_thresholds]

def calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds):
    user_points = initialize_points_database(user)
    current_points = user_points.get(user.id, 0)
    index = bisect_right(sorted_thresholds, current_points)
    current_threshold = sorted_thresholds[index - 1] if index > 0 else 0
    next_threshold = sorted_thresholds[index] if index < len(sorted_thresholds) else max(role_thresholds.keys())
    next_role_id = sorted_roles[index] if index < len(sorted_roles) else None
    next_rank_role = ctx.guild.get_role(next_role_id) if next_role_id else None
    next_rank_name = next_rank_role.name if next_rank_role else "Next Rank"
    points_needed = next_threshold - current_points if next_role_id else 0
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
    embed = disnake.Embed(
        title=title,
        description=f"Here's the current standing of __*{user.display_name}*__.",
        color=disnake.Color.green()
    )
    embed.add_field(name="\u200b", value=rank_text, inline=False)
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return embed