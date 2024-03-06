# modules.whiteboard

from modules.utils.commons import is_admin_or_rank
from disnake import TextInputStyle, ui
from disnake.ext import commands
import asyncio
import disnake

@commands.slash_command()
@is_admin_or_rank()
async def whiteboard(inter: disnake.ApplicationCommandInteraction):
    await inter.response.send_modal(
        title="Whiteboard",
        custom_id="whiteboard_modal",
        components=[
            ui.TextInput(
                label="Message ID",
                placeholder="Enter the message ID here (optional)",
                custom_id="message_id",
                style=TextInputStyle.single_line,
                value="None",
            ),
            ui.TextInput(
                label="Content",
                placeholder="Type your content here",
                custom_id="content",
                style=TextInputStyle.paragraph,
                value="",
            ),
        ],
    )
    try:
        modal_inter = await inter.bot.wait_for('interaction', check=lambda i: i.custom_id == 'whiteboard_modal' and i.author.id == inter.author.id, timeout=300)
        content = modal_inter.text_values.get('content', '')
        message_id = modal_inter.text_values.get('message_id', None)
        if message_id and message_id != "None":
            message_id = int(message_id)
            message = await inter.channel.fetch_message(message_id)
            await message.edit(content=content)
        else:
            await inter.channel.send(content=content)
        await modal_inter.response.defer()
        await modal_inter.delete_original_message()

    except asyncio.TimeoutError:
        return

def setup(client):
    client.add_slash_command(whiteboard)