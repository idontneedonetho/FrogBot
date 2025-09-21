# modules.emoji

from disnake import Embed, Color, RawReactionActionEvent, Message, User
from modules.utils.database import db_access_with_retry, update_points
from typing import List, Tuple, Dict, Optional, TypedDict
from disnake.ext import commands
import logging
import disnake
import asyncio

MAX_RETRIES: int = 3
RETRY_DELAY: int = 1

HEART_EMOJI: str = "❤️"
HEART_POINTS: int = 100
HEART_REASON: str = "being a good frog"

class ReplyInfo(TypedDict):
    reply_id: Optional[int]
    total_points: int
    reasons: List[Tuple[str, str]]

class EmojiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_replies: Dict[int, ReplyInfo] = {}
        self.reaction_lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        await self._process_reaction_event(payload, is_add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent) -> None:
        await self._process_reaction_event(payload, is_add=False)

    async def _process_reaction_event(self, payload: RawReactionActionEvent, is_add: bool) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        emoji_name = str(payload.emoji)
        async with self.reaction_lock:
            for _ in range(MAX_RETRIES):
                try:
                    if emoji_name == HEART_EMOJI:
                        await self.process_emoji_points(payload, is_add)
                    return
                except disnake.HTTPException as e:
                    if e.code == 429:
                        await asyncio.sleep(RETRY_DELAY)
                    else:
                        logging.error(f"HTTP error processing reaction: {e}")
                        return
                except Exception as e:
                    logging.error(f"Error processing reaction: {e}")
                    return

    async def process_emoji_points(self, payload: RawReactionActionEvent, is_add: bool) -> None:
        guild = self.bot.get_guild(payload.guild_id)
        reactor = guild.get_member(payload.user_id)
        if not reactor.guild_permissions.administrator:
            return
        message = await self.fetch_message(payload)
        user_id = message.author.id
        await self.update_user_points(user_id, is_add)
        await self.update_bot_reply(message, is_add)

    async def update_user_points(self, user_id: int, is_add: bool) -> int:
        points_to_change = HEART_POINTS
        user_points = await self.get_user_points(user_id)
        new_points = user_points + (points_to_change if is_add else -points_to_change)
        if await update_points(user_id, new_points):
            return new_points
        return user_points

    async def fetch_message(self, payload: RawReactionActionEvent) -> Message:
        channel = self.bot.get_channel(payload.channel_id)
        return await channel.fetch_message(payload.message_id)

    async def update_bot_reply(self, message: Message, is_add: bool) -> None:
        reply_info = self.bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
        reason_tuple = (HEART_EMOJI, HEART_REASON)
        if is_add and reason_tuple not in reply_info['reasons']:
            reply_info['reasons'].append(reason_tuple)
            reply_info['total_points'] += HEART_POINTS
        elif not is_add and reason_tuple in reply_info['reasons']:
            reply_info['reasons'].remove(reason_tuple)
            reply_info['total_points'] -= HEART_POINTS
        embed = self.create_points_embed(message.author, reply_info['total_points'], reply_info['reasons'])
        try:
            if reply_info['reply_id']:
                existing_reply = await message.channel.fetch_message(reply_info['reply_id'])
                await existing_reply.edit(embed=embed)
            else:
                new_reply = await message.reply(embed=embed)
                reply_info['reply_id'] = new_reply.id
            self.bot_replies[message.id] = reply_info
        except disnake.NotFound:
            new_reply = await message.reply(embed=embed)
            reply_info['reply_id'] = new_reply.id
            self.bot_replies[message.id] = reply_info
        except Exception as e:
            logging.error(f"Error updating bot reply: {e}")

    async def get_user_points(self, user_id: int) -> int:
        user_points_dict = await db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
        return user_points_dict[0][0] if user_points_dict else 0

    def create_points_embed(self, user: User, total_points: int, reasons: List[Tuple[str, str]]) -> Embed:
        embed = Embed(
            title="Points Updated",
            description=f"**{user.display_name}** has been awarded points for:",
            color=Color.green()
        )
        reasons_text = "\n".join([f"{emoji} {reason}" for emoji, reason in reasons])
        embed.add_field(name="Reasons", value=reasons_text, inline=False)
        embed.add_field(name="Total Points", value=str(total_points), inline=True)
        embed.set_footer(text=f"Updated on {disnake.utils.utcnow().strftime('%Y-%m-%d')} | Use '/check_points' for more info.")
        return embed

def setup(bot: commands.Bot) -> None:
    bot.add_cog(EmojiCog(bot))