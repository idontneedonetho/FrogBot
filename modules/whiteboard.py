# modules.whiteboard

from disnake import TextInputStyle, ui, Message, Embed, Color
from core import is_admin_or_privileged
from disnake.ext import commands

class WhiteboardCog(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.privileged_role_id = 1198482895342411846
        
    @commands.slash_command()
    async def whiteboard(self, inter):
        pass

    @whiteboard.sub_command(name="create")
    @is_admin_or_privileged(rank_id=1198482895342411846)
    async def create_whiteboard(self, inter):
        await self._handle_whiteboard(inter)

    @whiteboard.sub_command(name="edit")
    async def edit_by_id(self, inter, message_id):
        message = await inter.channel.fetch_message(int(message_id))
        await self._handle_edit(inter, message)

    @commands.message_command(name="Edit Whiteboard")
    async def edit_whiteboard(self, inter, message):
        await self._handle_edit(inter, message)

    async def _handle_edit(self, inter, message):
        if await self._can_edit_whiteboard(inter, message):
            await self._handle_whiteboard(inter, message)
        else:
            await inter.response.send_message("No edit permission", ephemeral=True)

    async def _can_edit_whiteboard(self, inter, message):
        if not message.embeds or message.author.id != self.client.user.id:
            return False
        
        has_permission = (inter.author.guild_permissions.administrator or 
                         any(role.id == self.privileged_role_id for role in inter.author.roles))
        
        if not has_permission and message.embeds[0].description:
            maintainer_section = message.embeds[0].description.split("**Whiteboard Maintainer(s):**")
            has_permission = len(maintainer_section) > 1 and f"<@{inter.author.id}>" in maintainer_section[1]
            
        return has_permission

    async def _handle_whiteboard(self, inter, message=None):
        embed = message.embeds[0] if message else None
        editor_id = None
        
        if embed and "\n\n**Whiteboard Maintainer(s):**" in embed.description:
            maintainer_section = embed.description.split("**Whiteboard Maintainer(s):**")[1]
            editor_id = ",".join(uid.strip("<@>") for uid in maintainer_section.split(", ") 
                               if uid.strip().startswith("<@") and not uid.strip().startswith("<@&"))

        modal = ui.Modal(
            title="Whiteboard",
            custom_id="whiteboard_modal",
            components=[
                ui.TextInput(label="Title", custom_id="title", style=TextInputStyle.short,
                           value=embed.title if embed else "Whiteboard"),
                ui.TextInput(label="Content", custom_id="content", style=TextInputStyle.paragraph,
                           value=embed.description.split("\n\n**Whiteboard")[0] if embed else None),
                ui.TextInput(label="Editor IDs (Optional, comma separated)", custom_id="editor_id", 
                           style=TextInputStyle.short, required=False, value=editor_id)
            ]
        )
        
        await inter.response.send_modal(modal)
        modal_inter = await inter.client.wait_for(
            'modal_submit',
            check=lambda i: i.custom_id == modal.custom_id and i.author.id == inter.author.id,
            timeout=600 if message else 1200
        )

        maintainers = [f"<@&{role.id}>" for role in inter.guild.roles if role.permissions.administrator]
        maintainers.append(f"<@&{self.privileged_role_id}>")
        
        if editor_id := modal_inter.text_values['editor_id']:
            maintainers.extend(f"<@{eid.strip()}>" for eid in editor_id.split(',') if eid.strip().isdigit())

        embed = Embed(
            title=modal_inter.text_values['title'],
            description=f"{modal_inter.text_values['content']}\n\n**Whiteboard Maintainer(s):**\n{', '.join(maintainers)}",
            color=Color.blue()
        )

        if message:
            await message.edit(embed=embed)
        else:
            await modal_inter.channel.send(embed=embed)
            
        await modal_inter.response.send_message(
            f"{'Updated' if message else 'Created'} successfully!", ephemeral=True)

def setup(client):
    client.add_cog(WhiteboardCog(client))
