# modules.whiteboard

from modules.utils.commons import is_admin_or_rank, send_long_message
from discord.ext import commands
import re

@commands.command(name="whiteboard")
@is_admin_or_rank()
async def whiteboard(ctx):
    content = extract_content_from_code_block(ctx.message.content)
    if content is None:
        await ctx.send("Please provide content in a code block.")
        return
    await send_long_message(ctx.message, content, should_reply=False)
    await ctx.message.delete()

@commands.command(name="edit")
@is_admin_or_rank()
async def edit(ctx):
    if ctx.message.reference is None:
        await ctx.send("Please reply to the message you want to edit.")
        return
    content = extract_content_from_code_block(ctx.message.content)
    if content is None:
        await ctx.send("Please provide content in a code block.")
        return
    message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    await message.edit(content=content)
    await ctx.message.delete()

def extract_content_from_code_block(message_content):
    match = re.search(r'```(.*)```', message_content, re.DOTALL)
    return match.group(1) if match else None

def setup(client):
    client.add_command(whiteboard)
    client.add_command(edit)