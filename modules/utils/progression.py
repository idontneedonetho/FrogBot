# modules.utils.progression

from modules.utils.database import initialize_points_database, get_user_points, db_access_with_retry
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
    1000000: 1471750837796864163
}

sorted_thresholds = sorted(role_thresholds.keys())
sorted_roles = [role_thresholds[threshold] for threshold in sorted_thresholds]

async def calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds):
    await initialize_points_database(user)
    current_points = await get_user_points(user.id)
    index = bisect_right(sorted_thresholds, current_points)
    current_threshold = sorted_thresholds[index - 1] if index > 0 else 0
    next_threshold = sorted_thresholds[index] if index < len(sorted_thresholds) else max(role_thresholds.keys())
    next_role_id = sorted_roles[index] if index < len(sorted_roles) else None
    next_rank_role = ctx.guild.get_role(next_role_id) if next_role_id else None
    next_rank_name = next_rank_role.name if next_rank_role else "Next Rank"
    points_needed = next_threshold - current_points if next_role_id else 0
    all_user_points = await get_all_users_points()
    sorted_users = sorted(all_user_points.items(), key=lambda x: x[1], reverse=True)
    user_rank = next((index for index, (u_id, _) in enumerate(sorted_users) if u_id == user.id), -1)
    return user_rank, next_rank_name, points_needed, current_threshold, next_threshold

async def get_all_users_points():
    rows = await db_access_with_retry('SELECT user_id, points FROM user_points')
    return {user_id: points for user_id, points in rows}

def create_progress_bar(current, total, length=10, fill_symbols='🟩🟨🟧🟥'):
    if total == 0:
        total = 1
    progress = current / total
    if progress == 0:
        return f"[{'⬜' * length}] 0.0%"
    filled_length = int(length * progress)
    fraction = (length * progress) % 1
    fractional_index = int(fraction * len(fill_symbols))
    bar = fill_symbols[0] * filled_length
    if filled_length < length:
        bar += fill_symbols[fractional_index]
        bar += '⬜' * (length - filled_length - 1)
    percentage = f"{progress * 100:.1f}%"
    return f"[{bar}] {percentage}"

async def create_points_embed(ctx, user, current_points, role_thresholds, action, user_rank, next_rank_name, points_changed, reason=None):
    title = f"Points Added ⬆️: {points_changed}" if action == "add" else f"Points Removed ⬇️: {points_changed}"
    user_rank, next_rank_name, points_needed, current_threshold, next_threshold = await calculate_user_rank_and_next_rank_name(ctx, user, role_thresholds)
    progress_length = next_threshold - current_threshold
    progress_current = current_points - current_threshold
    progress_bar = create_progress_bar(progress_current, progress_length)
    rank_emojis = ["🥇", "🥈", "🥉"]
    rank_display = rank_emojis[user_rank] if user_rank < 3 else f"#{user_rank + 1}"
    rank_text = f"**__{rank_display} | {user.display_name}: {current_points:,} points__**\nProgress: {progress_bar} ({points_needed:,} pts to {next_rank_name})"
    embed = disnake.Embed(
        title=title,
        description=reason if reason else None,
        color=disnake.Color.green()
    )
    embed.add_field(name="\u200b", value=rank_text, inline=False)
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    return embed
