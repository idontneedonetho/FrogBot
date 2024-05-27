# modules.emoji

import datetime
import asyncio
from contextlib import suppress
import disnake
from disnake import Button, ButtonStyle, ActionRow, Embed, ChannelType, Interaction
from modules.utils.database import db_access_with_retry, update_points
from modules.roles import check_user_points

bot_replies = {}

emoji_actions = {
    "✅": "handle_checkmark_reaction",
    "👍": "handle_thumbsup_reaction",
    "👎": "handle_thumbsdown_reaction"
}

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

async def handle_reaction(bot, payload, reaction_type, reply_message):
    """Handles general reaction events."""
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    if message.author != bot.user:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    required_rank_id = 1198482895342411846

    if not any(role.id >= required_rank_id for role in member.roles):
        return

    print(f"{reaction_type} reaction received from user {payload.user_id}")
    await message.reply(reply_message)

async def handle_thumbsup_reaction(bot, payload):
    """Handles thumbs up reaction event."""
    await handle_reaction(bot, payload, "Thumbs up", "Thank you for your positive feedback!")

async def handle_thumbsdown_reaction(bot, payload):
    """Handles thumbs down reaction event."""
    await handle_reaction(bot, payload, "Thumbs down", "We're sorry to hear that. We'll strive to do better.")

async def process_close(bot, payload):
    """Processes the close reaction."""
    if payload.user_id == bot.user.id or payload.guild_id is None:
        return

    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_actions:
        return

    message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
    if emoji_name == "✅" and ChannelType.forum and (payload.member.guild_permissions.administrator or payload.user_id == 126123710435295232):
        await handle_checkmark_reaction(bot, payload, message.author.id)

async def handle_checkmark_reaction(bot, payload, original_poster_id):
    """Handles checkmark reaction event."""
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    thread_id = message.thread.id
    guild = bot.get_guild(payload.guild_id)
    thread = disnake.utils.get(guild.threads, id=thread_id)

    embed = Embed(
        title="Resolution of Request/Report",
        description=f"<@{original_poster_id}>, your request or report is considered resolved. Are you satisfied with the resolution?",
        color=0x3498db
    )
    embed.set_footer(text="Selecting 'Yes' will close and delete this thread. Selecting 'No' will keep the thread open.")
    
    action_row = ActionRow(
        Button(style=ButtonStyle.success, label="Yes", custom_id=f"yes_{thread_id}"),
        Button(style=ButtonStyle.danger, label="No", custom_id=f"no_{thread_id}")
    )
    satisfaction_message = await channel.send(embed=embed, components=[action_row])
    
    # Save the interaction details to the database
    db_access_with_retry(
        "INSERT INTO interactions (message_id, user_id, thread_id, satisfaction_message_id, channel_id) VALUES (?, ?, ?, ?, ?)", 
        (message.id, original_poster_id, thread_id, satisfaction_message.id, payload.channel_id)
    )

    def check(interaction: Interaction):
        return interaction.message.id == satisfaction_message.id and interaction.user.id == original_poster_id

    async def send_reminder():
        await asyncio.sleep(43200)
        await channel.send(f"<@{original_poster_id}>, please select an option.")

    reminder_task = asyncio.create_task(send_reminder())

    try:
        interaction = await bot.wait_for("interaction", timeout=86400, check=check)
        thread = disnake.utils.get(guild.threads, id=thread_id)
        if interaction.component.label == "Yes":
            await interaction.response.send_message("Excellent! We're pleased to know you're satisfied. This thread will now be closed.")
            if thread:
                await thread.delete()
        else:
            await interaction.response.send_message("We're sorry to hear that. We'll strive to do better.")
    except asyncio.TimeoutError:
        await channel.send(f"<@{original_poster_id}>, you did not select an option within 24 hours. This thread will now be closed.")
        if thread:
            await thread.delete()
    finally:
        with suppress(asyncio.CancelledError):
            reminder_task.cancel()
        
        # Remove the interaction details from the database
        db_access_with_retry("DELETE FROM interactions WHERE thread_id = ?", (thread_id,))

async def process_emoji_reaction(bot, payload):
    """Processes emoji reactions for point allocation."""
    guild = bot.get_guild(payload.guild_id)
    reactor = guild.get_member(payload.user_id)
    if not reactor.guild_permissions.administrator:
        return

    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    user_id = message.author.id
    user_points = get_user_points(user_id)
    points_to_add = emoji_points.get(str(payload.emoji), 0)
    new_points = user_points + points_to_add

    if await update_points(user_id, new_points):
        await check_user_points(bot)
    
    await manage_bot_response(bot, payload, points_to_add, str(payload.emoji))

async def process_reaction(bot, payload):
    """Processes all types of reactions."""
    if payload.guild_id is None:
        return

    emoji_name = str(payload.emoji)
    if emoji_name in emoji_points:
        await process_emoji_reaction(bot, payload)
    elif emoji_name in emoji_actions:
        if emoji_name == "✅":
            await process_close(bot, payload)
        else:
            function_name = emoji_actions[emoji_name]
            function = globals()[function_name]
            await function(bot, payload)

def get_user_points(user_id):
    """Fetches user points from the database."""
    user_points_dict = db_access_with_retry('SELECT * FROM user_points WHERE user_id = ?', (user_id,))
    return user_points_dict[0][1] if user_points_dict else 0

async def manage_bot_response(bot, payload, points_to_add, emoji_name):
    """Manages bot responses to reactions."""
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
        except disnake.NotFound:
            bot_reply_info['reply_id'] = None

    if not bot_reply_info['reply_id']:
        bot_reply_message = await message.reply(embed=embed)
        bot_reply_info['reply_id'] = bot_reply_message.id

    bot_replies[message.id] = {'reply_id': bot_reply_message.id, 'total_points': total_points, 'reasons': bot_reply_info['reasons']}

def create_points_embed(user, total_points, reasons, emoji_name):
    """Creates an embed for points update."""
    title = f"Points Updated: {emoji_name}"
    description = f"{user.display_name} was awarded points for:"
    reason_to_emoji = {reason: emoji for emoji, reason in emoji_responses.items()}
    reasons_text = "\n".join([f"{reason_to_emoji.get(reason, '❓')} for {reason}" for reason in reasons])

    embed = disnake.Embed(
        title=title,
        description=description,
        color=disnake.Color.green()
    )
    embed.add_field(name="Reasons", value=reasons_text, inline=False)
    embed.add_field(name="Total Points", value=f"{total_points}", inline=True)
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d')} | '/check_points' for more info.")
    return embed

async def load_interaction_states(bot):
    """Loads interaction states from the database on startup."""
    interaction_states = db_access_with_retry("SELECT message_id, user_id, thread_id, satisfaction_message_id, channel_id FROM interactions")
    for state in interaction_states:
        message_id, user_id, thread_id, satisfaction_message_id, channel_id = state
        await resume_interaction(bot, message_id, user_id, thread_id, satisfaction_message_id, channel_id)

async def resume_interaction(bot, message_id, user_id, thread_id, satisfaction_message_id, channel_id):
    """Resumes monitoring an interaction after bot restart."""
    channel = bot.get_channel(channel_id)
    satisfaction_message = await channel.fetch_message(satisfaction_message_id)

    def check(interaction: Interaction):
        return interaction.message.id == satisfaction_message.id and interaction.user.id == user_id

    async def send_reminder():
        await asyncio.sleep(43200)
        await channel.send(f"<@{user_id}>, please select an option.")

    reminder_task = asyncio.create_task(send_reminder())

    try:
        interaction = await bot.wait_for("interaction", timeout=86400, check=check)
        thread = disnake.utils.get(channel.guild.threads, id=thread_id)
        if interaction.component.label == "Yes":
            await interaction.response.send_message("Excellent! We're pleased to know you're satisfied. This thread will now be closed.")
            if thread:
                await thread.delete()
        else:
            await interaction.response.send_message("We're sorry to hear that. We'll strive to do better.")
    except asyncio.TimeoutError:
        await channel.send(f"<@{user_id}>, you did not select an option within 24 hours. This thread will now be closed.")
        if thread:
            await thread.delete()
    finally:
        with suppress(asyncio.CancelledError):
            reminder_task.cancel()
        
        db_access_with_retry("DELETE FROM interactions WHERE thread_id = ?", (thread_id,))

def setup(client):
    """Sets up the client with event handlers."""
    @client.event
    async def on_ready():
        await load_interaction_states(client)
        print(f'Interaction states are loaded.')

    @client.event
    async def on_raw_reaction_add(payload):
        await process_reaction(client, payload)

    @client.event
    async def on_button_click(interaction: Interaction):
        custom_id = interaction.component.custom_id
        if custom_id.startswith("yes_") or custom_id.startswith("no_"):
            thread_id = int(custom_id.split("_")[1])
            thread = disnake.utils.get(interaction.guild.threads, id=thread_id)
            if custom_id.startswith("yes_"):
                await interaction.response.send_message("Excellent! We're pleased to know you're satisfied. This thread will now be closed.")
                if thread:
                    await thread.delete()
            else:
                await interaction.response.send_message("We're sorry to hear that. We'll strive to do better.")
            
            db_access_with_retry("DELETE FROM interactions WHERE thread_id = ?", (thread_id,))
