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

    print(f"Points added: {points_to_add} for {message.author.name} ({message.author.id})")
    new_reaction_message = f'{message.author.mention}{emoji_messages.get(emoji_name, "").format(points=points_to_add)}'

    # Check if the bot has already replied to this message
    bot_reply_info = bot_replies.get(message.id)
    if bot_reply_info:
        bot_reply_id = bot_reply_info['reply_id']
        try:
            bot_reply_message = await channel.fetch_message(bot_reply_id)
            # Append the new reaction message to the existing content
            new_reply_content = bot_reply_info['content'] + "\nAnd " + new_reaction_message
            await bot_reply_message.edit(content=new_reply_content)
            bot_replies[message.id]['content'] = new_reply_content  # Update stored content
        except discord.NotFound:
            # If the reply message was not found, reset the entry
            bot_replies[message.id] = None

    if not bot_replies.get(message.id):
        # Send a new reply and store the reply message ID and content
        bot_reply_message = await message.reply(new_reaction_message)
        bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'content': new_reaction_message}