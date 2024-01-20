# commands/emoji.py

import discord
import sqlite3

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
    "🧠": "making sure it was-well-thought out",
    "❤️": "being a good frog"
}

async def process_reaction(bot, payload, user_points):
    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_points:
        return

    if not await validate_reaction(bot, payload):
        return

    author_id, points_to_add = handle_points(payload, emoji_name, user_points)
    store_points(author_id, user_points[author_id])
    await manage_bot_response(bot, payload, author_id, points_to_add, emoji_name)

async def validate_reaction(bot, payload):
    guild = bot.get_guild(payload.guild_id)
    reactor = guild.get_member(payload.user_id)
    return reactor.guild_permissions.administrator

def handle_points(payload, emoji_name, user_points):
    author_id = payload.user_id
    points_to_add = emoji_points[emoji_name]
    user_points[author_id] = user_points.get(author_id, 0) + points_to_add
    return author_id, points_to_add

def store_points(author_id, total_points):
    with sqlite3.connect('user_points.db') as conn:
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (author_id, total_points))

async def manage_bot_response(bot, payload, author_id, points_to_add, emoji_name):
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    
    bot_reply_info = bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
    if emoji_responses[emoji_name] not in bot_reply_info['reasons']:
        bot_reply_info['reasons'].append(emoji_responses[emoji_name])

    active_responses = bot_reply_info['reasons']
    total_points = bot_reply_info['total_points'] + points_to_add
    response_text = build_response_text(message.author.mention, total_points, active_responses)

    if bot_reply_info['reply_id']:
        await update_existing_reply(channel, message, bot_reply_info, response_text)
    else:
        await send_new_reply(message, response_text, bot_reply_info, total_points)

async def update_existing_reply(channel, message, bot_reply_info, response_text):
    try:
        bot_reply_message = await channel.fetch_message(bot_reply_info['reply_id'])
        await bot_reply_message.edit(content=response_text)
        bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': bot_reply_info['total_points'], 'reasons': bot_reply_info['reasons']}
    except discord.NotFound:
        bot_replies[message.id] = None

async def send_new_reply(message, response_text, bot_reply_info, total_points):
    bot_reply_message = await message.reply(response_text)
    bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': total_points, 'reasons': bot_reply_info['reasons']}

def build_response_text(mention, total_points, active_responses):
    if not active_responses:
        return f"{mention} has been awarded {total_points} points."

    formatted_reasons = format_reasons(active_responses)
    return f"{mention} has been awarded {total_points} points for {formatted_reasons}"

def format_reasons(reasons):
    if len(reasons) > 1:
        return ', '.join(reasons[:-1]) + f", and {reasons[-1]}!"
    return reasons[0] + "!"
