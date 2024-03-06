# modules.reactions.close_thread

from disnake import Button, ButtonStyle, ActionRow, Interaction, Embed, ChannelType
from disnake.ui import Button, ActionRow
import disnake

emoji_actions = {
    "✅": "handle_checkmark_reaction"
}

async def process_reaction(bot, payload):
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
            await channel.delete()
    else:
        await interaction.response.send_message("We're sorry to hear that. We'll strive to do better.")

def setup(client):
    @client.event
    async def on_raw_reaction_add(payload):
        await process_reaction(client, payload)