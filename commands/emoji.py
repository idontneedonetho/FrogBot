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

    emoji_messages = {
        "🐞": " has been awarded {points} points for their bug report!",
        "📜": " has been awarded {points} points for including an error log in their bug report!",
        "📹": " has been awarded {points} points for including footage in their bug report!",
        "💡": " has been awarded {points} points for their feature request!",
        "🧠": " has been awarded {points} points for their well-thought-out feature request!",
        "❤️": " has been awarded {points} points for being a good frog!"
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

    def capitalize_sentences(message):
        sentences = message.split('!')
        if len(sentences) > 1:
            sentences[1] = sentences[1].strip().lower()
        capitalized_sentences = [sentences[0].strip().capitalize()]
        if len(sentences) > 1:
            capitalized_sentences.append(sentences[1])
        return ', '.join(capitalized_sentences) + '!'
    reaction_reason = emoji_messages.get(emoji_name, "").split(' for ')[1]
    
    bot_reply_info = bot_replies.get(message.id)
    if bot_reply_info:
        bot_reply_id = bot_reply_info['reply_id']
        try:
            bot_reply_message = await channel.fetch_message(bot_reply_id)
            total_points = bot_reply_info['total_points'] + points_to_add
            reasons = bot_reply_info['reasons'] + [reaction_reason]
            formatted_reasons = ' and '.join(reasons)
            combined_message = capitalize_sentences(f"@{message.author.display_name} has been awarded {total_points} points for {formatted_reasons}")
            await bot_reply_message.edit(content=combined_message)
            bot_replies[message.id] = {'reply_id': bot_reply_id, 'total_points': total_points, 'reasons': reasons}
        except discord.NotFound:
            bot_replies[message.id] = None
    
    if not bot_replies.get(message.id):
        bot_reply_message = await message.reply(f"@{message.author.display_name} has been awarded {points_to_add} points for {reaction_reason}")
        bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': points_to_add, 'reasons': [reaction_reason]}
