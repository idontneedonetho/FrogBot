# commons.py
import asyncio
import subprocess
from discord.ext import commands

async def fetch_reply_chain(message, max_tokens=8192):
    context = []
    tokens_used = 0
    current_prompt_tokens = len(message.content) // 4
    max_tokens -= current_prompt_tokens
    while message.reference is not None and tokens_used < max_tokens:
        try:
            message = await message.channel.fetch_message(message.reference.message_id)
            message_content = f"{message.content}\n"
            message_tokens = len(message_content) // 4
            if tokens_used + message_tokens <= max_tokens:
                context.append(message_content)
                tokens_used += message_tokens
            else:
                break
        except Exception as e:
            print(f"Error fetching reply chain message: {e}")
            break
    return context[::-1]

async def send_long_message(message, response):
    max_length = 2000
    if len(response) > max_length:
        parts = []
        while len(response) > max_length:
            split_index = response.rfind('\n', 0, max_length)
            if split_index == -1:
                split_index = max_length
            parts.append(response[:split_index])
            response = response[split_index:].strip()
        parts.append(response)
        last_message = None
        for part in parts:
            last_message = await (last_message.reply(part) if last_message else message.reply(part))
            await asyncio.sleep(1)
    else:
        await message.reply(response)
        
def get_git_version():
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()[:7]
        return f"v2.1 {branch} {commit}"
    except subprocess.CalledProcessError:
        return "v2.1 unknown-version"
frog_version = get_git_version()

def is_admin():
    async def predicate(ctx):
        author = ctx.message.author
        is_admin = author.guild_permissions.administrator
        print(f"Checking admin status for {author} (ID: {author.id}): {is_admin}")
        return is_admin
    return commands.check(predicate)

def is_admin_or_user(user_id=126123710435295232):
    async def predicate(ctx):
        is_admin = ctx.author.guild_permissions.administrator
        is_specific_user = ctx.author.id == user_id
        return is_admin or is_specific_user
    return commands.check(predicate)