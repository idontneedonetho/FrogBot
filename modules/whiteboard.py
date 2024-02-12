# Add this at the top of your file
from modules.utils.commons import is_admin_or_user, is_admin_or_rank, send_long_message
from discord.ext import commands

@commands.command(name="whiteboard")
@is_admin_or_user()
async def whiteboard(ctx):
    if not ctx.message.attachments or not ctx.message.attachments[0].filename.endswith('.txt'):
        await ctx.send("Please attach a .txt file.")
        return
    file = await ctx.message.attachments[0].read()
    content = file.decode()
    await send_long_message(ctx.message, content, first_message_is_reply=False)
    await ctx.message.delete()

@commands.command(name="edit")
@is_admin_or_rank()
async def edit(ctx):
    if ctx.message.reference is None:
        await ctx.send("Please reply to the message you want to edit.")
        return
    if not ctx.message.attachments or not ctx.message.attachments[0].filename.endswith('.txt'):
        await ctx.send("Please attach a .txt file.")
        return
    file = await ctx.message.attachments[0].read()
    content = file.decode()
    message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    messages_after = []
    async for msg in ctx.channel.history(after=message):
        messages_after.append(msg)
    for msg in messages_after:
        if msg.author == ctx.bot.user:
            await msg.delete()
        else:
            break
    await send_long_message(ctx.message, content, first_message_is_reply=False)
    await ctx.message.delete()

def setup(client):
    client.add_command(whiteboard)
    client.add_command(edit)