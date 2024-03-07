# modules.emoji

from disnake import Button, ButtonStyle, ActionRow, Interaction, Embed, ChannelType
from modules.utils.database import db_access_with_retry, update_points
from modules.roles import check_user_points
from disnake.ui import Button, ActionRow
import datetime
import disnake

bot_replies = {}

emoji_actions = {
    "✅": "handle_checkmark_reaction"
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

async def process_close(bot, payload):
    if payload.user_id == bot.user.id:
        return
    if payload.guild_id is None:
        return
    emoji_name = str(payload.emoji)
    if emoji_name not in emoji_actions:
        return
    message = await bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
    if emoji_name == "✅" and ChannelType.forum and (payload.member.guild_permissions.administrator or payload.user_id == 126123710435295232):
        await handle_checkmark_reaction(bot, payload, message.author.id)

async def handle_checkmark_reaction(bot, payload, original_poster_id):
    print(f"Handling checkmark reaction for user {original_poster_id}")
    channel = bot.get_channel(payload.channel_id)
    embed = Embed(title="Resolution of Request/Report",
                  description="Your request or report is considered resolved. Are you satisfied with the resolution?",
                  color=0x3498db)
    embed.set_footer(text="Selecting 'Yes' will close and delete this thread. Selecting 'No' will keep the thread open.")
    yes_button = Button(style=ButtonStyle.success, label="Yes")
    no_button = Button(style=ButtonStyle.danger, label="No")
    action_row = ActionRow(yes_button, no_button)
    satisfaction_message = await channel.send(embed=embed, components=[action_row])
    
    def check(interaction: Interaction):
        return interaction.message.id == satisfaction_message.id and interaction.user.id == original_poster_id

    interaction = await bot.wait_for("interaction", check=check)
    print(f"Interaction received from user {interaction.user.id}")
    if interaction.component.label == "Yes":
        await interaction.response.send_message("Excellent! We're pleased to know you're satisfied. This thread will now be closed.")
        if ChannelType.forum and channel.last_message_id == satisfaction_message.id:
            try:
                await channel.delete()
            except Exception as e:
                print(f"Error occurred while trying to delete channel: {e}")
    else:
        await interaction.response.send_message("We're sorry to hear that. We'll strive to do better.")

async def process_emoji_reaction(bot, payload):
    guild = bot.get_guild(payload.guild_id)
    reactor = guild.get_member(payload.user_id)
    if not reactor.guild_permissions.administrator:
        return
    channel = bot.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    user_id = message.author.id
    user_points = get_user_points(user_id)
    points_to_add = emoji_points[str(payload.emoji)]
    new_points = user_points + points_to_add
    if await update_points(user_id, new_points):
        await check_user_points(bot)
    await manage_bot_response(bot, payload, points_to_add, str(payload.emoji))

async def process_reaction(bot, payload):
    if payload.guild_id is None:
        return
    emoji_name = str(payload.emoji)
    if emoji_name in emoji_points:
        await process_emoji_reaction(bot, payload)
    elif emoji_name in emoji_actions:
        await process_close(bot, payload)

def get_user_points(user_id):
    user_points_dict = db_access_with_retry('SELECT * FROM user_points WHERE user_id = ?', (user_id,))
    return user_points_dict[0][1] if user_points_dict else 0

async def manage_bot_response(bot, payload, points_to_add, emoji_name):
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
    embed.set_footer(text=f"Updated on {datetime.datetime.now().strftime('%Y-%m-%d')} | '@FrogBot check points' for more info.")
    return embed

def setup(client):
    @client.event
    async def on_raw_reaction_add(payload):
        await process_reaction(client, payload)