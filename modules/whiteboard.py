# modules.whiteboard

from modules.utils.database import schedule_message, get_scheduled_message, get_user_scheduled_messages, cancel_scheduled_message
from disnake import TextInputStyle, ui, SelectOption
from core import is_admin_or_privileged
from disnake.ext import commands
from datetime import datetime
import dateutil.tz
import dateparser
import asyncio
import disnake
import pytz
import json


class WhiteboardModal(ui.Modal):
    def __init__(self, title="Whiteboard", default_values=None, include_scheduling=False):
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
            )
        ]
        if include_scheduling:
            components.extend([
                ui.TextInput(
                    label="Schedule Date/Time (Optional)",
                    custom_id="scheduled_time",
                    style=TextInputStyle.short,
                    placeholder="Examples: '3/24/2025 9am est', 'tomorrow 2pm', 'next monday 3pm' (leave empty for immediate)",
                    required=False,
                    value=self.default_values.get("scheduled_time", "")
                )
            ])
        super().__init__(
            title=title,
            custom_id="whiteboard_modal",
            timeout=1200,
            components=components
        )

class WhiteboardView(ui.View):
    def __init__(self, cog, message_data, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.message_data = message_data

    @ui.button(label="Edit", style=disnake.ButtonStyle.primary)
    async def edit_message(self, button: ui.Button, inter: disnake.MessageInteraction):
        if not await self.cog._can_edit_whiteboard(inter, self.message_data):
            await inter.response.send_message("You don't have permission to edit this message.", ephemeral=True)
            return
        scheduled_time = self.message_data.get("scheduled_time")
        if scheduled_time:
            tz = pytz.timezone(self.message_data.get("timezone", "UTC"))
            scheduled_time = scheduled_time.astimezone(tz).strftime("%m/%d/%Y %I:%M %p")
        modal = WhiteboardModal(
            title="Edit Whiteboard",
            default_values={
                "content": self.message_data["content"],
                "scheduled_time": scheduled_time,
                "channel": self.message_data.get("channel", "")
            },
            include_scheduling=True
        )
        try:
            await inter.response.send_modal(modal)
            modal_inter = await self.cog.client.wait_for(
                'modal_submit',
                check=lambda i: i.custom_id == modal.custom_id and i.author.id == inter.author.id,
                timeout=1200
            )
            await self._handle_modal_submit(modal_inter, inter)
        except asyncio.TimeoutError:
            await inter.followup.send("Timed out waiting for modal response.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"An error occurred while processing your edit: {str(e)}", ephemeral=True)

    async def _handle_modal_submit(self, modal_inter, inter):
        content = modal_inter.text_values['content']
        channel_input = modal_inter.text_values['channel'].strip()
        target_channel = await self._get_target_channel(inter, channel_input, modal_inter)
        if not target_channel:
            return
        scheduled_time = modal_inter.text_values.get('scheduled_time', '').strip()
        message_data = {
            "content": content,
            "channel": target_channel.mention
        }
        schedule_id = self.message_data.get("schedule_id")
        if schedule_id in self.cog.scheduled_tasks:
            self.cog.scheduled_tasks[schedule_id].cancel()
            del self.cog.scheduled_tasks[schedule_id]
        await cancel_scheduled_message(schedule_id)
        if scheduled_time:
            await self.cog._handle_scheduled_message(modal_inter, target_channel, content, scheduled_time, message_data)
        else:
            await self._handle_immediate_message(modal_inter, target_channel, content)

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

    async def _handle_immediate_message(self, modal_inter, target_channel, content):
        await self._split_and_send_message(content, target_channel, modal_inter)

    @ui.button(label="Cancel Schedule", style=disnake.ButtonStyle.danger)
    async def cancel_schedule(self, button: ui.Button, inter: disnake.MessageInteraction):
        if not await self.cog._can_edit_whiteboard(inter, self.message_data):
            await inter.response.send_message("You don't have permission to cancel this scheduled message.", ephemeral=True)
            return
        if "schedule_id" in self.message_data:
            await cancel_scheduled_message(self.message_data["schedule_id"])
            await inter.response.send_message("Scheduled message has been cancelled.", ephemeral=True)
        else:
            await inter.response.send_message("This message is not scheduled.", ephemeral=True)

class MessageSelect(ui.Select):
    def __init__(self, messages):
        options = []
        utc_fallback_used = False
        for msg in messages:
            try:
                scheduled_time_utc = datetime.fromisoformat(msg["scheduled_time"])
                if not scheduled_time_utc.tzinfo:
                    scheduled_time_utc = pytz.UTC.localize(scheduled_time_utc)
                tz_name = msg.get("timezone", "UTC")
                tz = None
                try:
                    tz = pytz.timezone(tz_name)
                except pytz.UnknownTimeZoneError:
                    if dateutil:
                        tz = dateutil.tz.gettz(tz_name)
                    if not tz:
                        print(f"Warning: Could not parse timezone '{tz_name}'. Defaulting to UTC for display.")
                        tz = pytz.UTC
                        utc_fallback_used = True
                local_time = scheduled_time_utc.astimezone(tz)
                description = f"Scheduled for {local_time.strftime('%m/%d/%Y %I:%M %p %Z')}"
                if tz == pytz.UTC and tz_name != "UTC" and utc_fallback_used:
                     description += f" (Original TZ '{tz_name}' unknown, showing UTC)"
                     utc_fallback_used = False
            except Exception as e:
                print(f"Error processing scheduled message ID {msg.get('id', 'N/A')} for display: {e}")
                local_time = datetime.fromisoformat(msg["scheduled_time"])
                description = f"Scheduled for {local_time.strftime('%m/%d/%Y %I:%M %p')} (Error parsing timezone)"
            label = "Whiteboard" if msg["is_whiteboard"] else "Message"
            options.append(SelectOption(
                label=label[:100],
                description=description,
                value=str(msg["id"])
            ))
        super().__init__(
            placeholder="Select a message to edit...",
            options=options,
            custom_id="message_select"
        )

    async def callback(self, inter):
        pass

class MessageSelectView(ui.View):
    def __init__(self, cog, messages, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.messages = messages
        self.add_item(MessageSelect(messages))

    async def interaction_check(self, inter) -> bool:
        message_id = int(inter.values[0])
        message = await get_scheduled_message(message_id)
        if not message:
            await inter.response.send_message("Message not found.", ephemeral=True)
            return False
        try:
            channel = inter.guild.get_channel(message["channel_id"])
            if channel:
                await self._cleanup_old_messages(channel, message)
        except Exception as e:
            print(f"Error cleaning up old message: {e}")
        try:
            whiteboard_data = json.loads(message["whiteboard_data"]) if message["whiteboard_data"] else {"content": message["content"]}
        except:
            whiteboard_data = {"content": message["content"]}
        scheduled_time = datetime.fromisoformat(message["scheduled_time"])
        tz = pytz.timezone(message["timezone"])
        local_time = scheduled_time.astimezone(tz)
        message_data = {
            "content": whiteboard_data.get("content", message["content"]),
            "scheduled_time": local_time,
            "timezone": message["timezone"],
            "schedule_id": message["id"]
        }
        message_text = await self.cog._create_whiteboard_text(message_data["content"])
        view = WhiteboardView(self.cog, message_data)
        await inter.response.send_message(
            content=message_text,
            view=view,
            ephemeral=True
        )
        return True

    async def _cleanup_old_messages(self, channel, message):
        async for msg in channel.history(limit=100):
            if msg.author == channel.guild.me:
                content = msg.content if msg.content else ""
                if message["is_whiteboard"]:
                    whiteboard_data = json.loads(message["whiteboard_data"]) if message["whiteboard_data"] else {"content": message["content"]}
                    if whiteboard_data.get("content", "").strip() in content:
                        first_message = msg
                        reference = msg.reference
                        while reference and reference.message_id:
                            try:
                                ref_message = await channel.fetch_message(reference.message_id)
                                if ref_message.author == channel.guild.me:
                                    first_message = ref_message
                                    reference = ref_message.reference
                                else:
                                    break
                            except:
                                break
                        related_messages = [first_message]
                        current_msg = first_message
                        async for chain_msg in channel.history(limit=20, after=first_message.created_at):
                            if (chain_msg.author == channel.guild.me and 
                                chain_msg.reference and chain_msg.reference.message_id == current_msg.id):
                                related_messages.append(chain_msg)
                                current_msg = chain_msg
                        for m in related_messages:
                            try:
                                await m.delete()
                            except Exception as e:
                                print(f"Error deleting message: {e}")
                        break
                elif message["content"] in content:
                    await msg.delete()
                    break

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
            print(f"Error restoring scheduled messages: {e}")

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
            print(f"Error sending scheduled message: {e}")
        finally:
            if message_data["id"] in self.scheduled_tasks:
                del self.scheduled_tasks[message_data["id"]]

    @commands.slash_command()
    async def whiteboard(self, inter):
        pass

    @whiteboard.sub_command(name="create")
    @is_admin_or_privileged(rank_id=1198482895342411846)
    async def create_whiteboard(self, inter):
        modal = WhiteboardModal(include_scheduling=True)
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

    async def _handle_modal_submit(self, modal_inter, inter):
        content = modal_inter.text_values['content']
        channel_input = modal_inter.text_values['channel'].strip()
        target_channel = await self._get_target_channel(inter, channel_input, modal_inter)
        if not target_channel:
            return
        scheduled_time = modal_inter.text_values.get('scheduled_time', '').strip()
        message_data = {
            "content": content,
        }
        if scheduled_time:
            await self._handle_scheduled_message(modal_inter, target_channel, content, scheduled_time, message_data)
        else:
            await self._handle_immediate_message(modal_inter, target_channel, content)

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
        message_text = await self._create_whiteboard_text(content)
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
                f"Whiteboard {'updated and ' if modal_inter.custom_id == 'edit_message_modal' else ''}sent successfully in {channel.mention}!",
                ephemeral=True
            )

    @whiteboard.sub_command(name="edit")
    @is_admin_or_privileged(rank_id=1198482895342411846)
    async def edit_whiteboard(self, inter):
        messages = await get_user_scheduled_messages(None)
        if not messages:
            await inter.response.send_message("There are no scheduled messages.", ephemeral=True)
            return
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
        view = MessageSelectView(self, future_messages)
        await inter.response.send_message(
            "Select a whiteboard to edit:",
            view=view,
            ephemeral=True
        )

    async def _can_edit_whiteboard(self, inter, message_data):
        return (inter.author.guild_permissions.administrator or 
                any(role.id == self.privileged_role_id for role in inter.author.roles))

    async def _create_whiteboard_text(self, content):
        return content.strip()

    @commands.message_command(name="Edit Message")
    async def edit_message_context(self, inter: disnake.MessageCommandInteraction):
        message = inter.target
        if message.author.id != self.client.user.id:
            await inter.response.send_message("I can only edit messages that I've sent.", ephemeral=True)
            return
        if not await self._can_edit_whiteboard(inter, {}):
            await inter.response.send_message("You don't have permission to edit this message.", ephemeral=True)
            return
        related_messages = await self._get_related_messages(message)
        full_content = "\n".join(msg.content for msg in related_messages)
        modal = ui.Modal(
            title="Edit Message",
            custom_id="edit_message_modal",
            components=[
                ui.TextInput(
                    label="Content",
                    custom_id="content",
                    style=TextInputStyle.paragraph,
                    value=full_content,
                    max_length=4000
                )
            ],
            timeout=1200
        )
        await inter.response.send_modal(modal)
        try:
            modal_inter = await self.client.wait_for(
                'modal_submit',
                check=lambda i: i.custom_id == modal.custom_id and i.author.id == inter.author.id,
                timeout=1200
            )
            content = modal_inter.text_values['content'].strip()
            for msg in related_messages:
                try:
                    await msg.delete()
                except Exception as e:
                    print(f"Error deleting message: {e}")
            await self._split_and_send_message(content, message.channel, modal_inter)
        except asyncio.TimeoutError:
            await inter.followup.send("Timed out waiting for modal response.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"An error occurred while processing your edit: {str(e)}", ephemeral=True)

    async def _get_related_messages(self, message):
        first_message = message
        reference = message.reference
        while reference and reference.message_id:
            try:
                ref_message = await message.channel.fetch_message(reference.message_id)
                if ref_message.author.id == self.client.user.id:
                    first_message = ref_message
                    reference = ref_message.reference
                else:
                    break
            except:
                break
        related_messages = [first_message]
        current_msg = first_message
        try:
            async for msg in message.channel.history(limit=20, after=first_message.created_at):
                if (msg.author.id == self.client.user.id and 
                    msg.reference and msg.reference.message_id == current_msg.id):
                    related_messages.append(msg)
                    current_msg = msg
        except Exception as e:
            print(f"Error finding related messages: {e}")
        return related_messages

    async def _handle_scheduled_message(self, modal_inter, target_channel, content, scheduled_time, message_data):
        try:
            settings = {'PREFER_DATES_FROM': 'future', 'RETURN_AS_TIMEZONE_AWARE': True}
            dt = dateparser.parse(scheduled_time, settings=settings)
            if not dt:
                await modal_inter.response.send_message(
                    "Could not parse the date/time. Please try a different format (e.g., 'MM/DD/YYYY HH:MM AM/PM Timezone', 'tomorrow 2pm EST').",
                    ephemeral=True
                )
                return
            if not dt.tzinfo:
                await modal_inter.response.send_message(
                    "Could not determine the timezone for the provided time. Please include a timezone (e.g., 'EST', 'PDT', 'America/New_York').",
                    ephemeral=True
                )
                return
            utc_dt = dt.astimezone(pytz.UTC)
            now = datetime.now(pytz.UTC)
            if utc_dt <= now:
                await modal_inter.response.send_message(
                    "Please schedule the message for a future time.",
                    ephemeral=True
                )
                return
            whiteboard_data = json.dumps(message_data)
            tz_str = getattr(dt.tzinfo, 'zone', None)
            if not tz_str:
                tz_str = dt.tzname()
            if not tz_str:
                tz_str = str(dt.tzinfo)
            schedule_id = await schedule_message(
                target_channel.id,
                modal_inter.author.id,
                content,
                utc_dt.isoformat(),
                tz_str,
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
                "whiteboard_data": whiteboard_data,
                "timezone": tz_str
            })
        except Exception as e:
            print(f"Error parsing/scheduling date/time: {e}")
            await modal_inter.response.send_message(
                f"Error parsing date/time: {str(e)}. Please try using a clear format like 'MM/DD/YYYY HH:MM AM/PM Timezone' or check bot logs.",
                ephemeral=True
            )

def setup(client):
    client.add_cog(WhiteboardCog(client))