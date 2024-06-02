# modules.on_thread_create

from disnake.ui import Button, View
import asyncio
import disnake

EMOJI_MAP = {
    1162100167110053888: ["🐞", "📜", "📹", "✅"],
    1167651506560962581: ["💡", "🧠", "✅"],
    1160318669839147259: ["💡", "🧠", "✅"],
}

async def add_reaction(message, emoji):
    try:
        await message.add_reaction(emoji)
        await asyncio.sleep(0.5)
    except Exception as e:
        print(f"Error adding reaction {emoji}: {e}")
        await asyncio.sleep(2)

class ConfirmationView(View):
    def __init__(self, message, original_poster_id):
        super().__init__()
        self.message = message
        self.original_poster_id = original_poster_id
        no_button = Button(style=disnake.ButtonStyle.green, label="Done!")
        no_button.callback = self.on_no_button_clicked
        self.add_item(no_button)
    async def on_no_button_clicked(self, interaction):
        if interaction.user.id != self.original_poster_id:
            return
        await self.message.delete()

async def on_thread_create(thread):
    try:
        await asyncio.sleep(1)
        emojis_to_add = EMOJI_MAP.get(thread.parent_id, [])

        first_non_bot_message = None
        async for message in thread.history(limit=None):
            if not message.author.bot:
                first_non_bot_message = message
                break
        if first_non_bot_message:
            await asyncio.gather(*(add_reaction(first_non_bot_message, emoji) for emoji in emojis_to_add))
        if thread.parent_id == 1162100167110053888:
            original_message = await thread.fetch_message(thread.id)
            message = await original_message.reply(
                "Greetings! It seems you're working on a bug report. To help you more effectively, could you please share the following details:\n"
                "- Did you check for updates? Your bug may already be fixed!\n"
                "- Are you on the “FrogPilot” or “FrogPilot-Staging” branch?\n"
                "- Was there an error in the error log? You can find this in the “Software” panel!\n"
                "- If you think it may be toggle related, post a copy of your toggles! You can find a copy of them in “Fleet Manager” in the “Tools” section!\n"
            )
            view = ConfirmationView(message, original_message.author.id)
            await message.edit(view=view)
    except Exception as e:
        print(f"Error in on_thread_create: {e}")

def setup(client):
    client.event(on_thread_create)
