# modules.utils.commons

import logging
import disnake
import re

async def send_message(message_or_channel, content, should_reply):
    try:
        if isinstance(message_or_channel, disnake.Message):
            if should_reply:
                return await (message_or_channel.send(content) if isinstance(message_or_channel, disnake.Thread) else message_or_channel.reply(content))
            else:
                return await message_or_channel.channel.send(content)
        elif isinstance(message_or_channel, (disnake.TextChannel, disnake.Thread)):
            return await message_or_channel.send(content)
        else:
            logging.error("Invalid input type for send_message. Expected disnake.Message, disnake.TextChannel, or disnake.Thread.")
            return None
    except Exception as e:
        logging.error(f"Error sending message: {e}")
        return None

def split_message(response, max_length=1950):
    parts = []
    current_part = ''
    code_block = False
    code_lang = ''
    for line in response.split('\n'):
        if line.startswith('```'):
            code_block = not code_block
            code_lang = line[3:] if code_block else ''
        if len(current_part) + len(line) + 1 > max_length:
            if code_block:
                current_part += '```\n'
                parts.append(current_part)
                current_part = f'```{code_lang}\n{line}\n'
            else:
                parts.append(current_part)
                current_part = line + '\n'
        else:
            current_part += line + '\n'
    if current_part:
        parts.append(current_part)
    return parts

def process_links(text):
    text = re.sub(r'\[([^\]]+)\]\((http[s]?://\S+)\)', r'\1 <\2>', text)
    return re.sub(r'(?<![<\(])http[s]?://\S+(?![>\)])', r'<\g<0>>', text)

async def send_long_message(message_or_channel, response, should_reply=True):
    try:
        response = process_links(response)
        parts = split_message(response)
        messages = []
        for i, part in enumerate(parts):
            if i == 0:
                last_message = await send_message(message_or_channel, part, should_reply)
            else:
                last_message = await send_message(last_message, part, False)
            if last_message is None:
                break
            messages.append(last_message)
        return messages
    except Exception as e:
        logging.error(f"Error in send_long_message: {e}")
        return None

def replace_mentions(content, mentions):
    for user in mentions:
        content = content.replace(f'<@{user.id}>', f'@{user.display_name}')
        content = content.replace(f'<@!{user.id}>', f'@{user.display_name}')
    return content

async def get_history_context(channel: disnake.abc.Messageable, token_limit: int = 8000) -> str:
    lines = []
    current_tokens = 0
    
    async for m in channel.history(limit=1000):
        if not m.content:
            continue
            
        line = f"{m.author.display_name}: {replace_mentions(m.content, m.mentions)}"
        # Heuristic: 1 token ≈ 4 characters
        tokens = len(line) // 4
        
        if current_tokens + tokens > token_limit:
            break
            
        lines.append(line)
        current_tokens += tokens
        
    # Return as single string with newest messages at the end
    return "\n".join(reversed(lines))