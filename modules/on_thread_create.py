# commands/thread_create_handler.py
import asyncio

async def on_thread_create(thread):
    try:
        await asyncio.sleep(0.1)
        if thread.parent_id == 1162100167110053888:
            emojis_to_add = ["🐞", "📜", "📹"]
        if thread.parent_id in [1167651506560962581, 1160318669839147259]:
            emojis_to_add = ["💡", "🧠"]
        first_message = await thread.fetch_message(thread.id)
        for emoji in emojis_to_add:
            await first_message.add_reaction(emoji)
    except Exception as e:
        print(f"Error in on_thread_create: {e}")
        
def setup(client):
    client.event(on_thread_create)