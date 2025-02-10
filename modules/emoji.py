# modules.emoji

from disnake import Embed, ButtonStyle, Color, PartialEmoji, RawReactionActionEvent, Message, Thread, User
from modules.utils.database import db_access_with_retry, update_points, log_checkmark_message_id
from disnake.ui import View, Button
from disnake.ext import commands
from typing import List, Tuple
import logging
import disnake
import asyncio
import time

ADMIN_USER_ID = 126123710435295232
ROLE_ID = 1221297807214776381

EMOJI_ACTIONS = {
    "✅": "handle_checkmark_reaction"
}

EMOJI_POINTS = {
    "🐞": 250, "📜": 250, "📹": 500,
    "💡": 100, "🧠": 250, "❤️": 100
}

EMOJI_RESPONSES = {
    "🐞": "their bug report",
    "📜": "submitting an error log",
    "📹": "including footage",
    "💡": "a feature request",
    "🧠": "making sure it was well-thought-out",
    "❤️": "being a good frog"
}

class EmojiCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_replies = {}
        self.reaction_lock = asyncio.Lock()
        self.max_retries = 3
        self.retry_delay = 1

    @commands.Cog.listener()
    async def on_ready(self):
        await self.reactivate_no_buttons()

    async def reactivate_no_buttons(self):
        rows = await db_access_with_retry('SELECT message_id, channel_id, timestamp FROM checkmark_logs')
        current_time = int(time.time())
        for row in rows:
            message_id, channel_id, timestamp = row
            channel = self.bot.get_channel(channel_id)
            if not channel:
                continue
            try:
                message = await channel.fetch_message(message_id)
                remaining_time = (7 * 24 * 60 * 60) - (current_time - timestamp)
                if remaining_time > 0:
                    view = self.ResolutionView(message, remaining_time)
                    await message.edit(view=view)
                    await view.start_countdown()
            except (disnake.NotFound, disnake.HTTPException):
                continue

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        await self.process_reaction(payload, is_add=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        await self.process_reaction(payload, is_add=False)

    async def process_reaction(self, payload: RawReactionActionEvent, is_add: bool):
        if payload.guild_id is None or payload.user_id == self.bot.user.id:
            return
        emoji_name = str(payload.emoji)
        async with self.reaction_lock:
            for _ in range(self.max_retries):
                try:
                    if emoji_name in EMOJI_POINTS:
                        await self.process_emoji_points(payload, is_add)
                    elif emoji_name in EMOJI_ACTIONS and is_add:
                        await getattr(self, EMOJI_ACTIONS[emoji_name])(payload)
                    break
                except disnake.errors.HTTPException as e:
                    if e.code == 429:
                        await asyncio.sleep(self.retry_delay)
                    else:
                        logging.error(f"HTTP error processing reaction: {e}")
                        break
                except Exception as e:
                    logging.error(f"Error processing reaction: {e}")
                    break

    async def process_emoji_points(self, payload: RawReactionActionEvent, is_add: bool):
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

    async def update_bot_reply(self, message: Message, total_points: int, emoji: str, is_add: bool):
        reply_info = self.bot_replies.get(message.id, {'reply_id': None, 'total_points': 0, 'reasons': []})
        reason_tuple = (emoji, EMOJI_RESPONSES[emoji])
        if is_add:
            if reason_tuple not in reply_info['reasons']:
                reply_info['reasons'].append(reason_tuple)
                reply_info['total_points'] += EMOJI_POINTS[emoji]
        else:
            if reason_tuple in reply_info['reasons']:
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
        except disnake.errors.NotFound:
            new_reply = await message.reply(embed=embed)
            reply_info['reply_id'] = new_reply.id
            self.bot_replies[message.id] = reply_info
        except Exception as e:
            logging.error(f"Error updating bot reply: {e}")

    async def find_existing_reply(self, message: Message) -> Message | None:
        async for msg in message.channel.history(limit=10, after=message):
            if (msg.author == self.bot.user and 
                msg.reference and 
                msg.reference.message_id == message.id and
                msg.embeds and 
                msg.embeds[0].title == "Points Updated"):
                return msg
        return None

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

    async def handle_checkmark_reaction(self, payload: RawReactionActionEvent):
        guild = self.bot.get_guild(payload.guild_id)
        user = guild.get_member(payload.user_id)
        authorized_role = guild.get_role(ROLE_ID)
        if user.guild_permissions.administrator or user.id == ADMIN_USER_ID or authorized_role in user.roles:
            channel = self.bot.get_channel(payload.channel_id)
            if isinstance(channel, Thread):
                message = await channel.fetch_message(payload.message_id)
                embed = Embed(
                    title="Issue/Request Resolution",
                    description="@here, this issue/request has been marked as *resolved!*\nNo further action is needed.\nThis thread will be automatically deleted in *7 days*.",
                    color=Color.green()
                )
                embed.set_footer(text="Please click 'Not Resolved' if this is incorrect.")
                view = self.ResolutionView(message)
                reply_message = await message.reply(embed=embed, view=view)
                current_timestamp = int(time.time())
                await log_checkmark_message_id(reply_message.id, channel.id, current_timestamp)
                await view.start_countdown()

    async def handle_feedback_reaction(self, payload: RawReactionActionEvent, title: str, description: str, color: Color):
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        if message.author.id == self.bot.user.id:
            embed = Embed(title=title, description=description, color=color)
            await message.reply(embed=embed)

    class ResolutionView(View):
        REMINDER_TIME = 5 * 24 * 60 * 60
        def __init__(self, message, remaining_time=None):
            super().__init__(timeout=None)
            self.message = message
            self.countdown_task = None
            self.remaining_time = remaining_time or (7 * 24 * 60 * 60)
            no_button = Button(style=ButtonStyle.red, label="Not Resolved", custom_id="not_resolved")
            no_button.callback = self.on_no_button_clicked
            self.add_item(no_button)
            close_button = Button(style=ButtonStyle.green, label="Close Now", custom_id="close_now")
            close_button.callback = self.on_close_button_clicked
            self.add_item(close_button)
        
        async def start_countdown(self):
            self.countdown_task = asyncio.create_task(self.countdown_with_reminder())
        
        async def countdown_with_reminder(self):
            await asyncio.sleep(self.REMINDER_TIME)
            await self.send_reminder()
            await asyncio.sleep(2 * 24 * 60 * 60)
            if isinstance(self.message.channel, Thread):
                await self.message.channel.delete()
                await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (self.message.id,))
        
        async def send_reminder(self):
            reminder_embed = Embed(
                title="Reminder",
                description="This thread will be closed in 2 days. If you need further assistance, please click 'Not Resolved'.",
                color=Color.orange()
            )
            await self.message.reply(embed=reminder_embed)
        
        async def on_no_button_clicked(self, interaction: disnake.MessageInteraction):
            if self.countdown_task:
                self.countdown_task.cancel()
            await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (self.message.id,))
            followup_embed = self.create_followup_embed()
            await interaction.edit_original_message(embed=followup_embed, view=None)
            await interaction.followup.send("The issue has been marked as unresolved. Please provide more details for further assistance.", ephemeral=True)
        
        async def on_close_button_clicked(self, interaction: disnake.MessageInteraction):
            if self.countdown_task:
                self.countdown_task.cancel()
            await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (self.message.id,))
            if isinstance(self.message.channel, Thread):
                await self.message.channel.delete()
        
        def create_followup_embed(self):
            return Embed(
                title="Further Assistance Needed",
                description="We're sorry that your issue/request was not resolved. Please provide more details for further assistance.",
                color=Color.red()
            )

def setup(bot):
    bot.add_cog(EmojiCog(bot))