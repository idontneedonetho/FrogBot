# modules.utils.frogpilot_sync

from modules.utils.database import get_all_users_points, sync_points_to_frogpilot
from disnake.ext import tasks, commands
import asyncio
import logging

class FrogPilotSyncCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sync_loop.start()

    def cog_unload(self):
        self.sync_loop.cancel()

    @tasks.loop(minutes=30)
    async def sync_loop(self):
        """Periodically sync all points to FrogPilot.com as a backup/baseline."""
        logging.info("Starting periodic point sync to FrogPilot.com...")
        try:
            all_points = await get_all_users_points()
            for user_id, points in all_points.items():
                await sync_points_to_frogpilot(user_id, points)
                # Small sleep to avoid hitting rate limits
                await asyncio.sleep(0.2)
            logging.info(f"Synced {len(all_points)} users to FrogPilot.com.")
        except Exception as e:
            logging.error(f"Error in point sync loop: {e}")

    @sync_loop.before_loop
    async def before_sync_loop(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(FrogPilotSyncCog(bot))
