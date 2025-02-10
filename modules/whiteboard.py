# modules.whiteboard

from modules.utils.database import schedule_message, get_scheduled_message, get_user_scheduled_messages, cancel_scheduled_message
from disnake import TextInputStyle, ui, SelectOption
from core import is_admin_or_privileged
from disnake.ext import commands
from datetime import datetime
import asyncio
import disnake
import pytz
import json

TIMEZONE_OPTIONS = {
    'UTC': 'UTC',
    'EST': 'US/Eastern',
    'CST': 'US/Central',
    'MST': 'US/Mountain',
    'PST': 'US/Pacific',
    'BST': 'Europe/London',
    'CET': 'Europe/Paris',
    'JST': 'Asia/Tokyo'
}

class WhiteboardModal(ui.Modal):
    def __init__(self, title="Whiteboard", default_values=None, include_scheduling=False):
        self.default_values = default_values or {}
        components = [
            ui.TextInput(
                label="Title (Optional)",
                custom_id="title",
                style=TextInputStyle.short,
                value=self.default_values.get("title", ""),
                required=False,
                placeholder="Leave empty for no title"
            ),
            ui.TextInput(
                label="Content",
                custom_id="content",
                style=TextInputStyle.paragraph,
                value=self.default_values.get("content", "")
            )
        ]
        if include_scheduling:
            components.extend([
                ui.TextInput(
                    label="Schedule Date/Time (Optional)",
                    custom_id="scheduled_time",
                    style=TextInputStyle.short,
                    placeholder="MM/DD/YYYY HH:MM AM/PM (leave empty for immediate)",
                    required=False,
                    value=self.default_values.get("scheduled_time", "")
                ),
                ui.TextInput(
                    label="Timezone",
                    custom_id="timezone",
                    style=TextInputStyle.short,
                    placeholder="UTC, EST, CST, MST, PST",
                    required=False,
                    value=self.default_values.get("timezone", "UTC")
                )
            ])
        components.append(
            ui.TextInput(
                label="Editor IDs (Optional, comma separated)",
                custom_id="editor_id",
                style=TextInputStyle.short,
                required=False,
                value=self.default_values.get("editor_id", "")
            )
        )
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
                "title": self.message_data["title"],
                "content": self.message_data["content"],
                "scheduled_time": scheduled_time,
                "timezone": self.message_data.get("timezone", "UTC"),
                "editor_id": ",".join(str(eid) for eid in self.message_data.get("editor_ids", []))
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
            title = modal_inter.text_values['title']
            content = modal_inter.text_values['content']
            editor_ids = [eid.strip() for eid in modal_inter.text_values.get('editor_id', '').split(',') if eid.strip()]
            scheduled_time = modal_inter.text_values.get('scheduled_time', '').strip()
            timezone_code = modal_inter.text_values.get('timezone', 'UTC').strip().upper()
            timezone, tz = await self.cog._validate_timezone(timezone_code)
            message_data = {
                "title": title,
                "content": content,
                "editor_ids": editor_ids
            }
            schedule_id = self.message_data.get("schedule_id")
            if schedule_id in self.cog.scheduled_tasks:
                self.cog.scheduled_tasks[schedule_id].cancel()
                del self.cog.scheduled_tasks[schedule_id]
            await cancel_scheduled_message(schedule_id)
            if scheduled_time:
                try:
                    dt = datetime.strptime(scheduled_time, "%m/%d/%Y %I:%M %p")
                    dt = tz.localize(dt)
                    utc_dt = dt.astimezone(pytz.UTC)
                    whiteboard_data = json.dumps(message_data)
                    new_schedule_id = await schedule_message(
                        inter.channel.id,
                        inter.author.id,
                        content,
                        utc_dt.isoformat(),
                        timezone,
                        True,
                        whiteboard_data
                    )
                    await modal_inter.response.send_message(
                        f"Whiteboard updated and rescheduled for {dt.strftime('%Y-%m-%d %I:%M %p %Z')}",
                        ephemeral=True
                    )
                    self.cog._schedule_message_task({
                        "id": new_schedule_id,
                        "channel_id": inter.channel.id,
                        "scheduled_time": utc_dt.isoformat(),
                        "is_whiteboard": True,
                        "whiteboard_data": whiteboard_data
                    })
                except ValueError:
                    await modal_inter.response.send_message(
                        "Invalid time format. Please use MM/DD/YYYY HH:MM AM/PM",
                        ephemeral=True
                    )
                    return
            else:
                message_text = await self.cog._create_whiteboard_text(title, content, editor_ids, inter)
                await modal_inter.channel.send(message_text)
                await modal_inter.response.send_message("Whiteboard updated and sent immediately!", ephemeral=True)
        except asyncio.TimeoutError:
            await inter.followup.send("Timed out waiting for modal response.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"An error occurred while processing your edit: {str(e)}", ephemeral=True)

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
        for msg in messages:
            scheduled_time = datetime.fromisoformat(msg["scheduled_time"])
            tz = pytz.timezone(msg["timezone"])
            local_time = scheduled_time.astimezone(tz)
            if msg["is_whiteboard"]:
                whiteboard_data = json.loads(msg["whiteboard_data"])
                label = whiteboard_data.get("title", "Whiteboard")
                description = f"Scheduled for {local_time.strftime('%m/%d/%Y %I:%M %p %Z')}"
            else:
                label = "Message"
                description = f"Scheduled for {local_time.strftime('%m/%d/%Y %I:%M %p %Z')}"
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
        if message["author_id"] != inter.author.id and not await self.cog._can_edit_whiteboard(inter, {"editor_ids": []}):
            await inter.response.send_message("You don't have permission to edit this message.", ephemeral=True)
            return False
        try:
            channel = inter.guild.get_channel(message["channel_id"])
            if channel:
                async for msg in channel.history(limit=100):
                    if msg.author == inter.guild.me:
                        content = msg.content if msg.content else ""
                        if message["is_whiteboard"]:
                            whiteboard_data = json.loads(message["whiteboard_data"])
                            if whiteboard_data.get("title", "") in content and whiteboard_data.get("content", "") in content:
                                await msg.delete()
                                break
                        elif message["content"] in content:
                            await msg.delete()
                            break
        except Exception as e:
            print(f"Error cleaning up old message: {e}")
        whiteboard_data = json.loads(message["whiteboard_data"]) if message["whiteboard_data"] else {}
        scheduled_time = datetime.fromisoformat(message["scheduled_time"])
        tz = pytz.timezone(message["timezone"])
        local_time = scheduled_time.astimezone(tz)
        message_data = {
            "title": whiteboard_data.get("title", "Whiteboard"),
            "content": whiteboard_data.get("content", ""),
            "editor_ids": whiteboard_data.get("editor_ids", []),
            "scheduled_time": local_time,
            "timezone": message["timezone"],
            "schedule_id": message["id"]
        }
        message_text = await self.cog._create_whiteboard_text(
            message_data["title"],
            message_data["content"],
            message_data["editor_ids"],
            inter
        )
        maintainers = await self.cog._get_maintainers_list(message_data["editor_ids"], inter)
        embed = disnake.Embed(
            title="Whiteboard Maintainers",
            description="\n".join(maintainers),
            color=disnake.Color.blue()
        )
        view = WhiteboardView(self.cog, message_data)
        await inter.response.send_message(
            content=message_text,
            embed=embed,
            view=view,
            ephemeral=True
        )
        return True

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
                message_text = await self._create_whiteboard_text(
                    whiteboard_data["title"],
                    whiteboard_data["content"],
                    whiteboard_data.get("editor_ids", []),
                    None
                )
                await channel.send(message_text)
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
            title = modal_inter.text_values['title']
            content = modal_inter.text_values['content']
            editor_ids = [eid.strip() for eid in modal_inter.text_values.get('editor_id', '').split(',') if eid.strip()]
            scheduled_time = modal_inter.text_values.get('scheduled_time', '').strip()
            timezone_code = modal_inter.text_values.get('timezone', 'UTC').strip().upper()
            timezone, tz = await self._validate_timezone(timezone_code)
            message_data = {
                "title": title,
                "content": content,
                "editor_ids": editor_ids
            }
            if scheduled_time:
                try:
                    dt = datetime.strptime(scheduled_time, "%m/%d/%Y %I:%M %p")
                    dt = tz.localize(dt)
                    utc_dt = dt.astimezone(pytz.UTC)
                    whiteboard_data = json.dumps(message_data)
                    schedule_id = await schedule_message(
                        inter.channel.id,
                        inter.author.id,
                        content,
                        utc_dt.isoformat(),
                        timezone,
                        True,
                        whiteboard_data
                    )
                    await modal_inter.response.send_message(
                        f"Whiteboard scheduled for {dt.strftime('%Y-%m-%d %I:%M %p %Z')}",
                        ephemeral=True
                    )
                    self._schedule_message_task({
                        "id": schedule_id,
                        "channel_id": inter.channel.id,
                        "scheduled_time": utc_dt.isoformat(),
                        "is_whiteboard": True,
                        "whiteboard_data": whiteboard_data
                    })
                except ValueError:
                    await modal_inter.response.send_message(
                        "Invalid time format. Please use MM/DD/YYYY HH:MM AM/PM",
                        ephemeral=True
                    )
                    return
            else:
                message_text = await self._create_whiteboard_text(title, content, editor_ids, inter)
                await modal_inter.channel.send(message_text)
                await modal_inter.response.send_message("Whiteboard created successfully!", ephemeral=True)
        except asyncio.TimeoutError:
            await inter.followup.send("Timed out waiting for modal response.", ephemeral=True)

    async def _create_whiteboard_text(self, title, content, editor_ids, inter=None):
        formatted_content = content.strip()
        if title.strip():
            return f"**{title.strip()}**\n\n{formatted_content}"
        return formatted_content

    async def _get_maintainers_list(self, editor_ids, inter):
        maintainers = []
        if inter:
            maintainers = [role.name for role in inter.guild.roles if role.permissions.administrator]
            privileged_role = inter.guild.get_role(self.privileged_role_id)
            if privileged_role:
                maintainers.append(privileged_role.name)
        return sorted(maintainers)

    async def _validate_timezone(self, timezone_code: str) -> tuple[str, pytz.timezone]:
        """Validate and return the timezone code and timezone object."""
        try:
            timezone = timezone_code.strip().upper()
            if timezone in TIMEZONE_OPTIONS:
                timezone = TIMEZONE_OPTIONS[timezone]
            tz = pytz.timezone(timezone)
            return timezone, tz
        except pytz.exceptions.UnknownTimeZoneError:
            return "UTC", pytz.UTC

    @whiteboard.sub_command(name="edit")
    async def edit_whiteboard(self, inter):
        messages = await get_user_scheduled_messages(inter.author.id)
        if not messages:
            await inter.response.send_message("You have no scheduled messages.", ephemeral=True)
            return
        now = datetime.now(pytz.UTC)
        future_messages = [
            msg for msg in messages 
            if datetime.fromisoformat(msg["scheduled_time"]) > now
        ]
        if not future_messages:
            await inter.response.send_message("You have no pending scheduled messages.", ephemeral=True)
            return
        view = MessageSelectView(self, future_messages)
        await inter.response.send_message(
            "Select a message to edit:",
            view=view,
            ephemeral=True
        )

    async def _can_edit_whiteboard(self, inter, message_data):
        has_permission = (inter.author.guild_permissions.administrator or 
                         any(role.id == self.privileged_role_id for role in inter.author.roles))
        if not has_permission and "editor_ids" in message_data:
            has_permission = str(inter.author.id) in message_data["editor_ids"]
        return has_permission

def setup(client):
    client.add_cog(WhiteboardCog(client))