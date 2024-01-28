# FrogBot/modules/emoji.py

from modules.utils.database import db_access_with_retry, initialize_points_database, update_points
from modules.roles import check_user_points
import discord
import datetime

bot_replies = {}

emoji_points = {
    "🐞": 250,
    "📜": 250,
    "📹": 500,
    "💡": 100,
    "🧠": 250,
    "❤️": 100
}

emoji_responses = {
    "🐞": "their bug report",
    "📜": "submitting an error log",
    "📹": "including footage",
    "💡": "a feature request",
    "🧠": "making sure it was well-thought-out",
    "❤️": "being a good frog"
}

async def on_raw_reaction_add(payload):
    if payload.guild_id:
        guild = bot.get_guild(payload.guild_id)
        bot = guild.me
        if payload.member and payload.member.guild_permissions.administrator:
            user = payload.member
            user_points_dict = initialize_points_database(user)
            user_points = user_points_dict.get(user.id, 0)
            await process_reaction(bot, payload, user_points)
            await check_user_points(bot)
        else:
            print(f"{payload.member.display_name} does not have the Administrator permission. Ignoring the reaction.")

async def process_reaction(bot, payload):
    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_points:
        return
    if not await validate_reaction(bot, payload):
        return
    user_id = payload.user_id
    user_points_dict = initialize_points_database(user_id)
    user_points = user_points_dict.get(user_id, 0)
    if not isinstance(user_points_dict, dict):
        print("user_points_dict is not a dictionary. This should not happen.")
        return
    author_id, points_to_add = handle_points(payload, emoji_name, user_points_dict)
    new_points = user_points + points_to_add
    if await update_points(author_id, new_points):
        await check_user_points(bot)
    await manage_bot_response(bot, payload, author_id, points_to_add, emoji_name)

async def validate_reaction(bot, payload):
    guild = bot.get_guild(payload.guild_id)
    reactor = guild.get_member(payload.user_id)
    return reactor.guild_permissions.administrator

def handle_points(payload, emoji_name, user_points_dict):
    author_id = payload.user_id
    points_to_add = emoji_points[emoji_name]
    current_points = user_points_dict.get(author_id, 0)
    user_points_dict[author_id] = current_points + points_to_add
    return author_id, points_to_add

def initialize_points_database(user_id):
    rows = db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
    if rows:
        return {user_id: rows[0][0]}
    else:
        db_access_with_retry('INSERT INTO user_points (user_id, points) VALUES (?, ?)', (user_id, 0))
        return {user_id: 0}

async def manage_bot_response(bot, payload, author_id, points_to_add, emoji_name):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    bot_reply_info = bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
    if emoji_responses[emoji_name] not in bot_reply_info['reasons']:
        bot_reply_info['reasons'].append(emoji_responses[emoji_name])
    total_points = bot_reply_info['total_points'] + points_to_add
    embed = create_points_embed(message.author, total_points, bot_reply_info['reasons'], emoji_name)
    if bot_reply_info['reply_id']:
        try:
            bot_reply_message = await channel.fetch_message(bot_reply_info['reply_id'])
            await bot_reply_message.edit(embed=embed)
            bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': total_points, 'reasons': bot_reply_info['reasons']}
        except:
            pass
    else:
        bot_reply_message = await message.reply(embed=embed)
        bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': total_points, 'reasons': bot_reply_info['reasons']}

def create_points_embed(user, total_points, reasons, emoji_name):
    title = f"Points Updated: {emoji_name}"
    description = f"{user.display_name} was awarded points for:"
    reason_to_emoji = {reason: emoji for emoji, reason in emoji_responses.items()}
    reasons_text = "\n".join([f"{reason_to_emoji.get(reason, '❓')} for {reason}" for reason in reasons])
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )
    embed.add_field(name="Reasons", value=reasons_text, inline=False)
    embed.add_field(name="Total Points", value=f"{total_points}", inline=True)
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d')} | @FrogBot check points for more")
    return embed

def setup(bot):
    @bot.event
    async def on_raw_reaction_add(payload):
        if payload.guild_id is None:
            return
        await process_reaction(bot, payload)