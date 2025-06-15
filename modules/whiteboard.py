# modules.whiteboard

from modules.utils.database import schedule_message, get_scheduled_message, get_user_scheduled_messages, cancel_scheduled_message, update_scheduled_message
from disnake import TextInputStyle, ui, SelectOption
from core import is_admin_or_privileged
from disnake.ext import commands
from datetime import datetime
import dateparser
import asyncio
import disnake
import logging
import pytz
import json

class WhiteboardModal(ui.Modal):
    def __init__(self, title="Whiteboard", default_values=None):
        self.default_values = default_values or {}
        components = [
            ui.TextInput(
                label="Content",
                custom_id="content",
                style=TextInputStyle.paragraph,
                value=self.default_values.get("content", ""),
                placeholder="Your content here..."
            ),
            ui.TextInput(
                label="Channel (Optional)",
                custom_id="channel",
                style=TextInputStyle.short,
                value=self.default_values.get("channel", ""),
                required=False,
                placeholder="Enter #channel-name or channel ID (leave empty for current channel)"
            ),
            ui.TextInput(
                label="Schedule Date/Time (Optional)",
                custom_id="scheduled_time",
                style=TextInputStyle.short,
                placeholder="Examples: '3/24/2025 9am est', 'tomorrow 2pm', 'next monday 3pm' (leave empty for immediate)",
                required=False,
                value=self.default_values.get("scheduled_time", "")
            )
        ]
        super().__init__(
            title=title,
            custom_id="whiteboard_modal",
            timeout=1200,
            components=components
        )

class WhiteboardCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.privileged_role_id = 1198482895342411846
        self.scheduled_tasks = {}
        
    async def cog_load(self):
        await self._restore_scheduled_messages()

    async def _restore_scheduled_messages(self):
        try:
            messages = await get_user_scheduled_messages(None)
            for msg in messages:
                if not msg["is_cancelled"]:
                    self._schedule_message_task(msg)
        except Exception as e:
            logging.error(f"Error restoring scheduled messages: {e}")

    def _schedule_message_task(self, message_data):
        scheduled_time = datetime.fromisoformat(message_data["scheduled_time"])
        now = datetime.now(pytz.UTC)
        delay = (scheduled_time - now).total_seconds()
        if delay > 0:
            task = asyncio.create_task(self._send_scheduled_message(message_data, delay))
            self.scheduled_tasks[message_data["id"]] = task

    async def _send_scheduled_message(self, message_data, delay):
        await asyncio.sleep(delay)
        try:
            channel = self.client.get_channel(message_data["channel_id"])
            if not channel:
                channel = await self.client.fetch_channel(message_data["channel_id"])
            if message_data["is_whiteboard"]:
                whiteboard_data = json.loads(message_data["whiteboard_data"])
                await self._split_and_send_message(whiteboard_data["content"], channel)
            else:
                await channel.send(message_data["content"])
            await cancel_scheduled_message(message_data["id"])
        except Exception as e:
            logging.error(f"Error sending scheduled message: {e}")
        finally:
            if message_data["id"] in self.scheduled_tasks:
                del self.scheduled_tasks[message_data["id"]]

    async def _parse_scheduled_time(self, time_str: str) -> tuple[datetime, str, datetime]:
        if not time_str:
            return None, None, None
        settings = {'PREFER_DATES_FROM': 'future', 'RETURN_AS_TIMEZONE_AWARE': True}
        dt = dateparser.parse(time_str, settings=settings)
        if not dt:
            raise ValueError("Could not parse the date/time. Please try a different format.")
        if not dt.tzinfo:
            raise ValueError("Could not determine the timezone. Please include a timezone (e.g., 'EST', 'PDT').")
        try:
            tz = pytz.timezone(dt.tzinfo.tzname(dt))
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC
        utc_dt = dt.astimezone(pytz.UTC)
        return utc_dt, tz.zone, dt

    async def _handle_modal_submit(self, modal_inter, inter):
        try:
            content = modal_inter.text_values['content'].strip()
            if not content:
                await modal_inter.response.send_message("Content cannot be empty.", ephemeral=True)
                return
            channel_input = modal_inter.text_values['channel'].strip()
            target_channel = await self._get_target_channel(inter, channel_input, modal_inter)
            if not target_channel:
                return
            scheduled_time_str = modal_inter.text_values.get('scheduled_time', '').strip()
            utc_dt, tz_name, dt = await self._parse_scheduled_time(scheduled_time_str)
            message_data = {
                "content": content,
                "channel": target_channel.mention
            }
            if utc_dt:
                whiteboard_data = json.dumps(message_data)
                schedule_id = await schedule_message(
                    target_channel.id,
                    modal_inter.author.id,
                    content,
                    utc_dt.isoformat(),
                    tz_name,
                    True,
                    whiteboard_data
                )
                await modal_inter.response.send_message(
                    f"Whiteboard scheduled for {dt.strftime('%Y-%m-%d %I:%M %p %Z')} in {target_channel.mention}",
                    ephemeral=True
                )
                self._schedule_message_task({
                    "id": schedule_id,
                    "channel_id": target_channel.id,
                    "scheduled_time": utc_dt.isoformat(),
                    "is_whiteboard": True,
                    "whiteboard_data": whiteboard_data
                })
            else:
                await self._split_and_send_message(content, target_channel, modal_inter)
        except ValueError as e:
            await modal_inter.response.send_message(str(e), ephemeral=True)
        except Exception as e:
            logging.error(f"Error handling whiteboard modal: {e}")
            await modal_inter.response.send_message(
                "An error occurred while processing your request. Please try again.",
                ephemeral=True
            )

    async def _get_target_channel(self, inter, channel_input, modal_inter):
        if not channel_input:
            return inter.channel
        if channel_input.startswith('#'):
            channel_name = channel_input[1:]
            target_channel = disnake.utils.get(inter.guild.channels, name=channel_name)
        elif channel_input.isdigit():
            try:
                target_channel = inter.guild.get_channel(int(channel_input))
            except:
                pass
        else:
            target_channel = None
        if not target_channel:
            await modal_inter.response.send_message(
                "Invalid channel. Please enter a valid channel name (e.g., #general) or channel ID.",
                ephemeral=True
            )
            return None
        return target_channel

    async def _split_and_send_message(self, content, channel, modal_inter=None):
        message_text = content.strip()
        parts = []
        current_part = ''
        for line in message_text.split('\n'):
            if len(current_part) + len(line) + 1 > 1950:
                parts.append(current_part)
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        if current_part:
            parts.append(current_part)
        last_message = None
        for i, part in enumerate(parts):
            if i == 0:
                last_message = await channel.send(part)
            else:
                last_message = await last_message.reply(part)
        if modal_inter:
            await modal_inter.response.send_message(
                f"Whiteboard sent successfully in {channel.mention}!",
                ephemeral=True
            )

    @commands.slash_command()
    async def whiteboard(self, inter):
        pass

    @whiteboard.sub_command(name="create")
    @is_admin_or_privileged(rank_id=1198482895342411846)
    async def create_whiteboard(self, inter):
        modal = WhiteboardModal()
        await inter.response.send_modal(modal)
        try:
            modal_inter = await self.client.wait_for(
                'modal_submit',
                check=lambda i: i.custom_id == modal.custom_id and i.author.id == inter.author.id,
                timeout=1200
            )
            await self._handle_modal_submit(modal_inter, inter)
        except asyncio.TimeoutError:
            await inter.followup.send("Timed out waiting for modal response.", ephemeral=True)

    @whiteboard.sub_command(name="edit")
    @is_admin_or_privileged(rank_id=1198482895342411846)
    async def edit_whiteboard(self, inter):
        messages = await get_user_scheduled_messages(None)
        now = datetime.now(pytz.UTC)
        future_messages = [
            msg for msg in messages 
            if datetime.fromisoformat(msg["scheduled_time"]) > now
            and not msg.get("is_cancelled", False)
            and msg["is_whiteboard"]
        ]
        if not future_messages:
            await inter.response.send_message("There are no pending scheduled whiteboards.", ephemeral=True)
            return
        options = []
        for msg in future_messages:
            try:
                scheduled_time = datetime.fromisoformat(msg["scheduled_time"])
                description = f"Scheduled for {scheduled_time.strftime('%m/%d/%Y %I:%M %p UTC')}"
            except Exception as e:
                logging.error(f"Error formatting time for message {msg['id']}: {e}")
                description = f"Scheduled for {msg['scheduled_time']}"
            options.append(SelectOption(
                label=f"Whiteboard {msg['id']}",
                description=description,
                value=str(msg["id"])
            ))
        select = ui.Select(
            placeholder="Select a whiteboard to manage...",
            options=options,
            custom_id="whiteboard_select"
        )
        async def select_callback(select_inter):
            message_id = int(select.values[0])
            message = await get_scheduled_message(message_id)
            edit_btn = ui.Button(label="Edit", style=disnake.ButtonStyle.primary)
            cancel_btn = ui.Button(label="Cancel", style=disnake.ButtonStyle.danger)

            async def edit_callback(btn_inter):
                try:
                    whiteboard_data = json.loads(message["whiteboard_data"]) if message["whiteboard_data"] else {"content": message["content"]}
                    modal = WhiteboardModal(
                        title="Edit Whiteboard",
                        default_values={
                            "content": whiteboard_data.get("content", message["content"]),
                            "scheduled_time": datetime.fromisoformat(message["scheduled_time"]).strftime("%Y-%m-%d %H:%M:%S"),
                            "channel": str(message.get("channel_id", ""))
                        }
                    )
                    modal.custom_id = f"edit_modal_{message_id}"
                    await btn_inter.response.send_modal(modal)
                    try:
                        modal_inter = await self.client.wait_for(
                            'modal_submit',
                            check=lambda i: i.custom_id == modal.custom_id and i.author.id == btn_inter.author.id,
                            timeout=1200
                        )
                        await self._handle_edit_submit(modal_inter, btn_inter, message_id)
                    except asyncio.TimeoutError:
                        await btn_inter.followup.send("Timed out waiting for modal response.", ephemeral=True)
                except Exception as e:
                    logging.error(f"Error editing whiteboard: {e}")
                    await btn_inter.response.send_message("An error occurred. Please try again.", ephemeral=True)

            async def cancel_callback(btn_inter):
                try:
                    await cancel_scheduled_message(message_id)
                    if message_id in self.scheduled_tasks:
                        self.scheduled_tasks[message_id].cancel()
                        del self.scheduled_tasks[message_id]
                    await btn_inter.response.send_message("✅ Whiteboard cancellation successful!", ephemeral=True)
                except Exception as e:
                    logging.error(f"Error cancelling whiteboard: {e}")
                    await btn_inter.response.send_message("Failed to cancel whiteboard. Please try again.", ephemeral=True)
            edit_btn.callback = edit_callback
            cancel_btn.callback = cancel_callback
            view = ui.View()
            view.add_item(edit_btn)
            view.add_item(cancel_btn)
            await select_inter.response.send_message(
                f"Manage whiteboard originally scheduled for {datetime.fromisoformat(message['scheduled_time']).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                view=view,
                ephemeral=True
            )
        select.callback = select_callback
        view = ui.View()
        view.add_item(select)
        await inter.response.send_message("Select a whiteboard to manage:", view=view, ephemeral=True)

    async def _handle_edit_submit(self, modal_inter, inter, message_id):
        try:
            if message_id in self.scheduled_tasks:
                self.scheduled_tasks[message_id].cancel()
                del self.scheduled_tasks[message_id]
            content = modal_inter.text_values['content'].strip()
            channel_input = modal_inter.text_values['channel'].strip()
            target_channel = await self._get_target_channel(inter, channel_input, modal_inter)
            scheduled_time_str = modal_inter.text_values.get('scheduled_time', '').strip()
            utc_dt, tz_name, dt = await self._parse_scheduled_time(scheduled_time_str)
            success = await update_scheduled_message(
                id=message_id,
                content=content,
                scheduled_time=utc_dt.isoformat(),
                timezone=tz_name,
                whiteboard_data=json.dumps({"content": content, "channel": target_channel.mention})
            )
            if not success:
                raise Exception("Database update failed")
            self._schedule_message_task({
                "id": message_id,
                "channel_id": target_channel.id,
                "scheduled_time": utc_dt.isoformat(),
                "is_whiteboard": True,
                "whiteboard_data": json.dumps({"content": content, "channel": target_channel.mention})
            })
            await modal_inter.response.send_message(
                f"✅ Whiteboard updated! New schedule: {dt.strftime('%Y-%m-%d %I:%M %p %Z')} in {target_channel.mention}",
                ephemeral=True
            )
        except Exception as e:
            logging.error(f"Error handling edit submission: {e}")
            await modal_inter.response.send_message("Failed to update whiteboard. Please try again.", ephemeral=True)

def setup(client):
    client.add_cog(WhiteboardCog(client))