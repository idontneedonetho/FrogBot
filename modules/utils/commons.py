# modules.utils.commons

from llama_index.core.llms import MessageRole as Role
from disnake.ext import commands
from disnake.utils import get
import subprocess
import asyncio
import re

async def fetch_message_from_link(client, link):
    match = re.match(r'https://discord.com/channels/(\d+)/(\d+)/(\d+)', link)
    if match:
        guild_id, channel_id, message_id = map(int, match.groups())
        guild = get(client.guilds, id=guild_id)
        if guild:
            channel = get(guild.channels, id=channel_id)
            if channel:
                try:
                    message = await channel.fetch_message(message_id)
                    return message
                except Exception as e:
                    print(f"Error fetching message from link: {e}")
    return None

class HistoryChatMessage:
    def __init__(self, content, role, additional_kwargs=None):
        self.content = content
        self.role = role
        self.additional_kwargs = additional_kwargs if additional_kwargs else {}

async def fetch_reply_chain(message, max_tokens=4096):
    context = []
    tokens_used = 0
    current_prompt_tokens = len(message.content) // 4
    max_tokens -= current_prompt_tokens
    while message.reference is not None and tokens_used < max_tokens:
        try:
            message = await message.channel.fetch_message(message.reference.message_id)
            role = Role.USER if message.author.bot else Role.ASSISTANT
            message_content = f"{message.content}\n"
            message_tokens = len(message_content) // 4
            if tokens_used + message_tokens <= max_tokens:
                context.append(HistoryChatMessage(message_content, role))
                tokens_used += message_tokens
            else:
                break
        except Exception as e:
            print(f"Error fetching reply chain message: {e}")
            break
    return context[::-1]

async def send_message(message, content, should_reply):
    if should_reply:
        return await message.reply(content)
    else:
        return await message.channel.send(content)

def split_message(response):
    max_length = 2000
    markdown_chars = ['*', '_', '~', '|']
    parts = []
    code_block_type = None
    while len(response) > max_length:
        split_index = response.rfind('\n', 0, max_length)
        split_index = max_length - 1 if split_index == -1 else split_index
        code_block_start = response.rfind('```', 0, split_index)
        if code_block_start != -1:
            newline_after_code_block_start = response.find('\n', code_block_start)
            if newline_after_code_block_start != -1 and newline_after_code_block_start < split_index:
                code_block_type = response[code_block_start+3:newline_after_code_block_start].strip()
            code_block_end = response.find('```', code_block_start + 3)
            if code_block_end == -1 or code_block_end > split_index:
                part = response[:split_index+1] + '```'
                response = '```' + (code_block_type + '\n' if code_block_type else '') + response[split_index+1:].lstrip()
            else:
                part = response[:split_index+1]
                response = response[split_index+1:].lstrip()
        else:
            part = response[:split_index+1]
            response = response[split_index+1:].lstrip()
        for char in markdown_chars:
            if part.count(char) % 2 != 0 and not part.endswith('```'):
                part += char
                response = char + response
        parts.append(part.rstrip())
    parts.append(response.rstrip())
    return parts

def replace_wiki_links(response):
    response = re.sub(r'openpilot\.wiki', '<https://github.com/commaai/openpilot/wiki', response)
    response = re.sub(r'\.md', '>', response)
    return response

async def send_long_message(message, response, should_reply=True):
    response = re.sub(r'\((http[s]?://\S+)\)', r'(<\1>)', response)
    response = re.sub(r'(?<![\(<])http[s]?://\S+(?![>\)])', r'<\g<0>>', response)
    response = replace_wiki_links(response)
    messages = []
    parts = split_message(response)
    for part in parts:
        last_message = await send_message(message, part, should_reply)
        messages.append(last_message)
        message = last_message
    return messages

def get_git_version():
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()[:7]
        return f"v2.2 {branch} {commit}"
    except subprocess.CalledProcessError:
        return "unknown-version"
bot_version = get_git_version()

def is_admin():
    async def predicate(ctx):
        author = ctx.user
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

def is_admin_or_rank(rank_id=1198482895342411846):
    async def predicate(ctx):
        is_admin = ctx.author.guild_permissions.administrator
        has_rank = any(role.id == rank_id for role in ctx.author.roles)
        return is_admin or has_rank
    return commands.check(predicate)