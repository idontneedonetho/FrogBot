# modules.thread_controls

from modules.utils.database import db_access_with_retry, update_points, log_checkmark_message_id
from core import is_admin_or_privileged, CONFIG
from disnake import Embed, Color, ButtonStyle
from dataclasses import dataclass
from disnake.ext import commands
from typing import Dict
import logging
import disnake
import asyncio
import time

@dataclass
class Config:
    ROLE_ID: int = 1221297807214776381
    RESOLUTION_WINDOW: int = 7 * 24 * 60 * 60
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 1

BUTTON_POINTS: Dict[str, int] = {
    "report": 250,
    "error_log": 250, 
    "evidence": 500,
    "close": 0
}

BUTTON_RESPONSES: Dict[str, str] = {
    "report": "their bug report",
    "error_log": "submitting an error log",
    "evidence": "including footage",
    "close": "closing the thread"
}

class ThreadControlsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot_replies: Dict[int, dict] = {}

    @commands.slash_command(name="thread_actions", description="Manage thread actions with buttons")
    @is_admin_or_privileged(user_id=CONFIG['ADMIN_USER_ID'], rank_id=Config.ROLE_ID)
    async def thread_actions(self, inter: disnake.ApplicationCommandInteraction):
        if not isinstance(inter.channel, disnake.Thread):
            await inter.response.send_message("This command can only be used in threads.", ephemeral=True)
            return
        class ThreadActionsView(disnake.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
                self.add_item(disnake.ui.Button(
                    style=ButtonStyle.primary,
                    label="Report",
                    custom_id="button_report",
                    emoji="🐞"
                ))
                self.add_item(disnake.ui.Button(
                    style=ButtonStyle.primary,
                    label="Error Log", 
                    custom_id="button_error_log",
                    emoji="📜"
                ))
                self.add_item(disnake.ui.Button(
                    style=ButtonStyle.primary,
                    label="Evidence",
                    custom_id="button_evidence", 
                    emoji="📹"
                ))
                self.add_item(disnake.ui.Button(
                    style=ButtonStyle.danger,
                    label="Close",
                    custom_id="button_close",
                    emoji="✅"
                ))
        embed = Embed(
            title="Thread Actions",
            description="Use the buttons below to manage this thread:",
            color=Color.blue()
        )
        embed.add_field(
            name="Actions Available",
            value="🐞 **Report** - Mark as bug report (250 pts)\n"
                  "📜 **Error Log** - Mark as error log submission (250 pts)\n"
                  "📹 **Evidence** - Mark as evidence submission (500 pts)\n"
                  "✅ **Close** - Mark thread as resolved",
            inline=False
        )
        await inter.response.send_message(
            embed=embed,
            view=ThreadActionsView(),
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith("button_"):
            return
        authorized_role = inter.guild.get_role(Config.ROLE_ID)
        if not (inter.author.guild_permissions.administrator or 
                inter.author.id == CONFIG['ADMIN_USER_ID'] or 
                authorized_role in inter.author.roles):
            await inter.response.send_message("You don't have permission to use this.", ephemeral=True)
            return
        if not isinstance(inter.channel, disnake.Thread):
            await inter.response.send_message("This can only be used in threads.", ephemeral=True)
            return
        button_type = inter.component.custom_id.replace("button_", "")
        if button_type == "close":
            await self.handle_close_button(inter)
        elif button_type in BUTTON_POINTS:
            await self.handle_points_button(inter, button_type)
        else:
            await inter.response.send_message("Unknown button action.", ephemeral=True)

    async def handle_close_button(self, inter: disnake.MessageInteraction):
        embed = Embed(
            title="Issue/Request Resolution",
            description="@here, this issue/request has been marked as *resolved!*\nNo further action is needed.\nThis thread will be automatically deleted in *7 days*.",
            color=Color.green()
        )
        embed.set_footer(text="Thread will be automatically closed in 7 days.")
        reply_message = await inter.channel.send(embed=embed)
        current_timestamp = int(time.time())
        await log_checkmark_message_id(reply_message.id, inter.channel.id, current_timestamp)
        asyncio.create_task(self.resolution_countdown(reply_message, inter.channel.id))
        await inter.response.defer()

    async def handle_points_button(self, inter: disnake.MessageInteraction, button_type: str):
        thread_owner = inter.channel.owner
        if not thread_owner:
            await inter.response.send_message("Could not find thread owner.", ephemeral=True)
            return
        points = BUTTON_POINTS[button_type]
        reason = BUTTON_RESPONSES[button_type]
        current_points = await self.get_user_points(thread_owner.id)
        new_points = current_points + points
        await update_points(thread_owner.id, new_points)
        thread_id = inter.channel.id
        if thread_id not in self.bot_replies:
            self.bot_replies[thread_id] = {'message_id': None, 'total_points': 0, 'reasons': []}
        reply_info = self.bot_replies[thread_id]
        reason_tuple = (button_type, reason)
        reply_info['reasons'].append(reason_tuple)
        reply_info['total_points'] += points
        embed = Embed(
            title="Points Awarded",
            description=f"**{thread_owner.display_name}** has been awarded points for:",
            color=Color.green()
        )
        reasons_text = "\n".join([f"🐞 {reason}" if button_type == "report" else 
                                  f"📜 {reason}" if button_type == "error_log" else 
                                  f"📹 {reason}" if button_type == "evidence" else 
                                  f"✅ {reason}" for button_type, reason in reply_info['reasons']])
        embed.add_field(name="Reasons", value=reasons_text, inline=False)
        embed.add_field(name="Total Points Awarded", value=str(reply_info['total_points']), inline=True)
        embed.set_footer(text=f"Awarded by {inter.author.display_name}")
        try:
            if reply_info['message_id']:
                existing_message = await inter.channel.fetch_message(reply_info['message_id'])
                await existing_message.edit(embed=embed)
            else:
                new_message = await inter.channel.send(embed=embed)
                reply_info['message_id'] = new_message.id
        except disnake.NotFound:
            new_message = await inter.channel.send(embed=embed)
            reply_info['message_id'] = new_message.id
        except Exception as e:
            logging.error(f"Error updating points embed: {e}")
            new_message = await inter.channel.send(embed=embed)
            reply_info['message_id'] = new_message.id
        await inter.response.defer()

    async def get_user_points(self, user_id: int) -> int:
        user_points_dict = await db_access_with_retry('SELECT points FROM user_points WHERE user_id = ?', (user_id,))
        return user_points_dict[0][0] if user_points_dict else 0

    async def resolution_countdown(self, message: disnake.Message, channel_id: int) -> None:
        try:
            await asyncio.sleep(5 * 24 * 60 * 60)  # 5 days
            results = await db_access_with_retry('SELECT message_id FROM checkmark_logs WHERE message_id = ?', (message.id,))
            if not results:
                return
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
            try:
                reminder_embed = Embed(
                    title="Reminder",
                    description="@here, this thread will be closed in 2 days. If you need further assistance, please contact a moderator.",
                    color=Color.orange()
                )
                await message.reply(embed=reminder_embed)
            except:
                pass
            await asyncio.sleep(2 * 24 * 60 * 60)  # 2 days
            results = await db_access_with_retry('SELECT message_id FROM checkmark_logs WHERE message_id = ?', (message.id,))
            if not results:
                return
            if isinstance(channel, disnake.Thread):
                await db_access_with_retry('DELETE FROM checkmark_logs WHERE message_id = ?', (message.id,))
                await channel.delete()
        except Exception as e:
            logging.error(f"Error in resolution countdown: {e}")

def setup(bot: commands.Bot) -> None:
    bot.add_cog(ThreadControlsCog(bot))