# modules.llm.utils.utils

from modules.llm.utils.config import IMAGE_MAX_SIZE, VIDEO_SIZE_LIMIT
from typing import Optional, Dict
from google import genai
from io import BytesIO
from PIL import Image
import logging
import aiohttp
import disnake
import re

logger = logging.getLogger(__name__)

def _resize_image_if_needed(image: Image.Image, max_dimensions: int) -> Image.Image:
    if max(image.size) > max_dimensions:
        ratio = max_dimensions / max(image.size)
        new_size = tuple(int(dim * ratio) for dim in image.size)
        try:
            resized_image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.debug(f"Resized image from {image.size} to {new_size}")
            return resized_image
        except Exception as e:
            logger.error(f"Failed to resize image: {e}")
            return image
    return image

def format_discord_message(msg, discord_client) -> dict:
    return {
        "author": msg.author.display_name,
        "content": re.sub(
            r'<@!?(\d+)>',
            lambda m: f'@{discord_client.get_user(int(m.group(1))).display_name or "UnknownUser"}',
            msg.content
        ),
        "is_bot": msg.author.bot,
        "mentioned_users": [user.display_name for user in msg.mentions],
        "has_bot_mention": discord_client.user.mentioned_in(msg),
        "channel_name": msg.channel.name,
        "timestamp": msg.created_at.strftime("%I:%M %p")
    }

async def process_media(attachment) -> Optional[genai.types.Part]:
    try:
        if attachment.content_type.startswith('image/'):
            image_data = await attachment.read()
            image = Image.open(BytesIO(image_data))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            image = _resize_image_if_needed(image, IMAGE_MAX_SIZE)
            return image
        elif attachment.content_type.startswith('video/'):
            if attachment.size > VIDEO_SIZE_LIMIT:
                logger.warning(f"Video {attachment.filename} exceeds size limit")
                return None
            video_data = await attachment.read()
            return genai.types.Part.from_bytes(
                data=video_data,
                mime_type=attachment.content_type
            )
    except Exception as e:
        logger.error(f"Error processing media attachment {attachment.filename}: {e}")
        return None

def is_youtube_url(url: str) -> bool:
    youtube_patterns = [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([^&\s]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([^&\s]+)'
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)

async def process_url(url: str) -> Optional[genai.types.Part]:
    try:
        if is_youtube_url(url):
             return genai.types.Part(file_data=genai.types.FileData(file_uri=url, mime_type="video/mp4"))
        elif any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        image = Image.open(BytesIO(image_data))
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        image = _resize_image_if_needed(image, IMAGE_MAX_SIZE)
                        return image
                    else:
                        logger.warning(f"Failed to fetch image URL {url}, status: {response.status}")
                        return None
        else:
            return None
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        return None

async def convert_mentions(text: str, message: disnake.Message) -> str:
    if not message.guild:
        logger.debug("Cannot convert mentions, not in a guild.")
        return text    
    potential_names = set(re.findall(r'@([\w\\.-]+)', text))
    if not potential_names:
        return text
    mention_map: Dict[str, int] = {}
    ambiguous_or_missing: set[str] = set()
    logger.debug(f"Mention Conversion: Potential names found: {potential_names}")
    members_in_guild = message.guild.members
    for name_to_find in potential_names:
        matches = []
        name_lower = name_to_find.lower()
        for member in members_in_guild:
            if (member.display_name.lower() == name_lower or \
                member.name.lower() == name_lower or \
                (member.global_name and member.global_name.lower() == name_lower)):\
                matches.append(member.id)
        if len(matches) == 1:
            user_id = matches[0]
            mention_map[name_to_find] = user_id
            logger.info(f"Mention Conversion: Successfully mapped @{name_to_find} -> <@{user_id}>")
        elif len(matches) > 1:
            ambiguous_or_missing.add(name_to_find)
            logger.warning(f"Mention Conversion: Ambiguous mention @{name_to_find}. Multiple users match: {matches}. Leaving as text.")
        else:
            ambiguous_or_missing.add(name_to_find)
            logger.warning(f"Mention Conversion: Could not find any user matching @{name_to_find}. Leaving as text.")

    def replace_mention(match):
        original_name = match.group(1)
        user_id = mention_map.get(original_name)
        if user_id:
            return f"<@{user_id}>"
        else:
            logger.debug(f"Mention Conversion: Replacing ambiguous/missing mention '@{original_name}' with just '{original_name}'.")
            return original_name
    converted_text = re.sub(r'(?<!<)@((?!\d+>)[\w\\.-]+)', replace_mention, text)
    return converted_text 