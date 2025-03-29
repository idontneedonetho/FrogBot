# modules.emoji

from modules.utils.database import db_access_with_retry, update_points, log_checkmark_message_id
from disnake import Embed, Color, PartialEmoji, RawReactionActionEvent, Message, Thread, User
from typing import List, Tuple, Dict, Optional, TypedDict
from dataclasses import dataclass
from disnake.ext import commands
import logging
import disnake
import asyncio
import time


@dataclass
class Config:
    ADMIN_USER_ID: int = 126123710435295232
    ROLE_ID: int = 1221297807214776381
    RESOLUTION_WINDOW: int = 7 * 24 * 60 * 60
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1

EMOJI_ACTIONS: Dict[str, str] = {
    "✅": "handle_checkmark_reaction",
    "❌": "handle_x_reaction"
}

EMOJI_POINTS: Dict[str, int] = {
    "🐞": 250, "📜": 250, "📹": 500,
    "💡": 100, "🧠": 250, "❤️": 100
}

EMOJI_RESPONSES: Dict[str, str] = {
    "🐞": "their bug report",
    "📜": "submitting an error log",
    "📹": "including footage",
    "💡": "a feature request",
    "🧠": "making sure it was well-thought-out",
    "❤️": "being a good frog"
}

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
    async def on_ready(self) -> None:
        await self.reactivate_resolution_messages()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        await self._process_reaction_event(payload, is_add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent) -> None:
        await self._process_reaction_event(payload, is_add=False)

    async def reactivate_resolution_messages(self) -> None:
        rows = await db_access_with_retry('SELECT message_id, channel_id, timestamp FROM checkmark_logs')
        current_time = int(time.time())
        for row in rows:
            message_id, channel_id, timestamp = row
            if not (channel := self.bot.get_channel(channel_id)):
                continue
            try:
                message = await channel.fetch_message(message_id)
                await self._validate_resolution_reactions(message, current_time, timestamp)
            except (disnake.NotFound, disnake.HTTPException):
                continue

    async def _process_reaction_event(self, payload: RawReactionActionEvent, is_add: bool) -> None:
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        emoji_name = str(payload.emoji)
        async with self.reaction_lock:
            for _ in range(Config.MAX_RETRIES):
                try:
                    if emoji_name == "🗑️" and is_add:
                        await self._handle_trash_reaction(payload)
                    elif emoji_name in EMOJI_POINTS:
                        await self.process_emoji_points(payload, is_add)
                    elif emoji_name in EMOJI_ACTIONS and is_add:
                        await getattr(self, EMOJI_ACTIONS[emoji_name])(payload)
                    return
                except disnake.HTTPException as e:
                    if e.code == 429:
                        await asyncio.sleep(Config.RETRY_DELAY)
                    else:
                        logging.error(f"HTTP error processing reaction: {e}")
                        return
                except Exception as e:
                    logging.error(f"Error processing reaction: {e}")
                    return

    async def _validate_resolution_reactions(self, message: Message, current_time: int, timestamp: int) -> None:
        remaining_time = Config.RESOLUTION_WINDOW - (current_time - timestamp)
        if remaining_time <= 0:
            return
        has_x, has_trash = await self._check_reactions(message)
        await self._update_resolution_embed(message, has_x, has_trash)
        asyncio.create_task(self.resolution_countdown(message, message.channel.id))

    async def _check_reactions(self, message: Message) -> Tuple[bool, bool]:
        has_x = has_trash = False
        for reaction in message.reactions:
            emoji_str = str(reaction.emoji)
            if emoji_str == "❌":
                has_x = True
            elif emoji_str == "🗑️":
                has_trash = True
        return has_x, has_trash

    async def _update_resolution_embed(self, message: Message, has_x: bool, has_trash: bool) -> None:
        if message.embeds and "React with" not in message.embeds[0].footer.text:
            embed = message.embeds[0]
            embed.set_footer(text="React with ❌ if this is incorrect or 🗑️ to close now.")
            await message.edit(embed=embed)
        for emoji, needed in [("❌", not has_x), ("🗑️", not has_trash)]:
            if needed:
                await message.add_reaction(emoji)

    async def process_emoji_points(self, payload: RawReactionActionEvent, is_add: bool) -> None:
        guild = self.bot.get_guild(payload.guild_id)
        reactor = guild.get_member(payload.user_id)
        if not reactor.guild_permissions.administrator:
            return
        message = await self.fetch_message(payload)
        user_id = message.author.id
        new_points = await self.update_user_points(user_id, payload.emoji, is_add)
        await self.update_bot_reply(message, new_points, str(payload.emoji), is_add)

    async def update_user_points(self, user_id: int, emoji: PartialEmoji, is_add: bool) -> int:
        points_to_change = EMOJI_POINTS[str(emoji)]
        user_points = await self.get_user_points(user_id)
        new_points = user_points + (points_to_change if is_add else -points_to_change)
        if await update_points(user_id, new_points):
            return new_points
        return user_points

    async def fetch_message(self, payload: RawReactionActionEvent) -> Message:
        channel = self.bot.get_channel(payload.channel_id)
        return await channel.fetch_message(payload.message_id)

    async def update_bot_reply(self, message: Message, total_points: int, emoji: str, is_add: bool) -> None:
        reply_info = self.bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
        reason_tuple = (emoji, EMOJI_RESPONSES[emoji])
        if is_add and reason_tuple not in reply_info['reasons']:
            reply_info['reasons'].append(reason_tuple)
            reply_info['total_points'] += EMOJI_POINTS[emoji]
        elif not is_add and reason_tuple in reply_info['reasons']:
            reply_info['reasons'].remove(reason_tuple)
            reply_info['total_points'] -= EMOJI_POINTS[emoji]
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

    async def handle_checkmark_reaction(self, payload: RawReactionActionEvent) -> None:
        guild = self.bot.get_guild(payload.guild_id)
        user = guild.get_member(payload.user_id)
        authorized_role = guild.get_role(Config.ROLE_ID)
        if not (user.guild_permissions.administrator or user.id == Config.ADMIN_USER_ID or authorized_role in user.roles):
            return
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, Thread):
            return
        message = await channel.fetch_message(payload.message_id)
        embed = Embed(
            title="Issue/Request Resolution",
            description="@here, this issue/request has been marked as *resolved!*\nNo further action is needed.\nThis thread will be automatically deleted in *7 days*.",
            color=Color.green()
        )
        embed.set_footer(text="React with ❌ if this is incorrect or 🗑️ to close now.")
        reply_message = await message.reply(embed=embed)
        await reply_message.add_reaction("❌")
        await reply_message.add_reaction("🗑️")
        current_timestamp = int(time.time())
        await log_checkmark_message_id(reply_message.id, channel.id, current_timestamp)
        asyncio.create_task(self.resolution_countdown(reply_message, channel.id))

    async def handle_x_reaction(self, payload: RawReactionActionEvent) -> None:
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        message = await channel.fetch_message(payload.message_id)
        guild = self.bot.get_guild(payload.guild_id)
        user = guild.get_member(payload.user_id)
        authorized_role = guild.get_role(Config.ROLE_ID)
        if not (user.guild_permissions.administrator or user.id == Config.ADMIN_USER_ID or authorized_role in user.roles):
            try:
                await message.remove_reaction("❌", user)
            except:
                pass
            return
        await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (message.id,))
        followup_embed = Embed(
            title="Further Assistance Needed",
            description="We're sorry that your issue/request was not resolved. Please provide more details for further assistance.",
            color=Color.red()
        )
        await message.clear_reactions()
        await message.edit(embed=followup_embed)

    async def resolution_countdown(self, message: Message, channel_id: int) -> None:
        try:
            await asyncio.sleep(5 * 24 * 60 * 60)
            results = await db_access_with_retry('SELECT message_id FROM checkmark_logs WHERE message_id = ?', (message.id,))
            if not results:
                return
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
            try:
                reminder_embed = Embed(
                    title="Reminder",
                    description="This thread will be closed in 2 days. If you need further assistance, please react with ❌.",
                    color=Color.orange()
                )
                await message.reply(embed=reminder_embed)
            except:
                pass
            await asyncio.sleep(2 * 24 * 60 * 60)
            results = await db_access_with_retry('SELECT message_id FROM checkmark_logs WHERE message_id = ?', (message.id,))
            if not results:
                return
            if isinstance(channel, Thread):
                await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (message.id,))
                await channel.delete()
        except Exception as e:
            logging.error(f"Error in resolution countdown: {e}")

    async def _handle_trash_reaction(self, payload: RawReactionActionEvent) -> None:
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        try:
            message = await channel.fetch_message(payload.message_id)
            if message.author.id != self.bot.user.id:
                return
            guild = self.bot.get_guild(payload.guild_id)
            user = guild.get_member(payload.user_id)
            authorized_role = guild.get_role(Config.ROLE_ID)
            if not (user.guild_permissions.administrator or user.id == Config.ADMIN_USER_ID or authorized_role in user.roles):
                try:
                    await message.remove_reaction("🗑️", user)
                except disnake.HTTPException:
                    pass
                return
            await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (message.id,))
            if isinstance(channel, Thread):
                await channel.delete()
        except disnake.HTTPException as e:
            logging.error(f"Error handling trash reaction: {e}")

def setup(bot: commands.Bot) -> None:
    bot.add_cog(EmojiCog(bot))