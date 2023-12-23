# commands/emoji.py

import discord
import sqlite3
bot_replies = {}

async def process_reaction(bot, payload, user_points):
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
        "📜": "an error log",
        "📹": "footage",
        "💡": "a feature request",
        "🧠": "a well-thought-out feature request",
        "❤️": "being a good frog"
    }

    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_points:
        return

    guild_id = payload.guild_id
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    guild = bot.get_guild(guild_id)
    reactor = guild.get_member(payload.user_id)

    if not reactor.guild_permissions.administrator:
        return

    author_id = message.author.id
    points_to_add = emoji_points[emoji_name]
    user_points[author_id] = user_points.get(author_id, 0) + points_to_add

    conn = sqlite3.connect('user_points.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO user_points (user_id, points) VALUES (?, ?)', (author_id, user_points[author_id]))
    conn.commit()
    conn.close()

    bot_reply_info = bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
    if emoji_responses[emoji_name] not in bot_reply_info['reasons']:
        bot_reply_info['reasons'].append(emoji_responses[emoji_name])

    active_responses = bot_reply_info['reasons']
    if bot_reply_info['reply_id']:
        try:
            bot_reply_message = await channel.fetch_message(bot_reply_info['reply_id'])
            total_points = bot_reply_info['total_points'] + points_to_add
            response_parts = []
            for reason in active_responses:
                if reason == active_responses[-1]:  # Last reason
                    response_parts.append(f"{reason}!")
                else:
                    response_parts.append(f"{reason},")
            combined_reasons = " and ".join(response_parts)
            combined_message = f"{message.author.mention} has been awarded {total_points} points for {combined_reasons}"
            await bot_reply_message.edit(content=combined_message)
            bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': total_points, 'reasons': active_responses}
        except discord.NotFound:
            bot_replies[message.id] = None
    else:
        if active_responses:
            response_parts = [f"{active_responses[0]}!"]
        else:
            response_parts = [""]
        combined_reasons = " and ".join(response_parts)
        bot_reply_message = await message.reply(f"{message.author.mention} has been awarded {points_to_add} points for {combined_reasons}")
        bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': points_to_add, 'reasons': active_responses}

