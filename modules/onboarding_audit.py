# modules.onboarding_audit.py

from core import Config, CONFIG, is_admin_or_privileged
from datetime import datetime, timedelta, timezone
from disnake.ext import commands, tasks
import asyncio
import disnake
import logging

PHOENIX_TZ = timezone(timedelta(hours=-7))
DEADLINE_KICK_DATETIME = datetime(2025, 8, 6, 14, 3, 10, tzinfo=PHOENIX_TZ)

class OnboardingAuditCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config_data = Config(CONFIG['CONFIG_FILE']).read()
        self.tadpole_role_id = self.config_data.get('TADPOLE_ROLE_ID', 0)
        self.role_clear_target_ids = self.config_data.get('ROLE_CLEAR_TARGET_IDS', [])
        self.enable_24h_onboarding_kick = self.config_data.get('ENABLE_24H_ONBOARDING_KICK', False)
        self.onboarding_kick_activation_timestamp_float = self.config_data.get('ONBOARDING_KICK_ACTIVATION_TIMESTAMP', 0.0)
        if self.onboarding_kick_activation_timestamp_float > 0.0:
            self.onboarding_kick_activation_timestamp = datetime.fromtimestamp(self.onboarding_kick_activation_timestamp_float, tz=timezone.utc)
        else:
            self.onboarding_kick_activation_timestamp = None
        if not hasattr(self.bot, 'config_data'):
            self.bot.config_data = self.config_data
        if not self.tadpole_role_id:
            logging.error("Onboarding/Audit Cog: Tadpole Role ID is not configured. Core functionality might be impaired.")
        else:
            if self.enable_24h_onboarding_kick:
                self.check_pending_onboarding_task.start()
                logging.info("24h onboarding kick task started due to ENABLE_24H_ONBOARDING_KICK=true.")
            else:
                logging.info("24h onboarding kick task NOT started due to ENABLE_24H_ONBOARDING_KICK=false.")
            self.deadline_kick_task.start()
        logging.info(f"OnboardingAuditCog initialized. Tadpole Role ID: {self.tadpole_role_id}")

    def cog_unload(self):
        self.check_pending_onboarding_task.cancel()
        self.deadline_kick_task.cancel()

    @tasks.loop(hours=1)
    async def check_pending_onboarding_task(self):
        await self.bot.wait_until_ready()
        if not self.enable_24h_onboarding_kick:
            return
        if self.onboarding_kick_activation_timestamp is None:
            logging.debug("24h onboarding kick: Enabled but no valid activation timestamp set. Task will do nothing until /toggle_onboarding_kick sets it.")
            return
        now_utc = datetime.now(timezone.utc)
        if now_utc < self.onboarding_kick_activation_timestamp:
            logging.debug(f"24h onboarding kick: Waiting for activation time {self.onboarding_kick_activation_timestamp} to pass. Current time: {now_utc}")
            return
        logging.info(f"Running hourly check for pending onboarding (rule active since {self.onboarding_kick_activation_timestamp})...")
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            logging.error("Pending onboarding check: Guild not found.")
            return
        if not self.tadpole_role_id:
            logging.warning("Pending onboarding check: Tadpole role ID not set. Skipping.")
            return
        now = datetime.now(timezone.utc)
        kick_threshold = now - timedelta(hours=24)
        for member in guild.members:
            if member.bot:
                continue
            joined_at_utc = member.joined_at.astimezone(timezone.utc) if member.joined_at else None
            if not joined_at_utc:
                logging.warning(f"Member {member.id} ({member.display_name}) has no join timestamp. Skipping.")
                continue
            if joined_at_utc < self.onboarding_kick_activation_timestamp:
                continue
            if joined_at_utc < kick_threshold:
                has_tadpole_role = any(role.id == self.tadpole_role_id for role in member.roles)
                if not has_tadpole_role:
                    logging.info(f"Kicking member {member.id} ({member.display_name}) for not completing onboarding within 24 hours (missing Tadpole role).")
                    try:
                        await member.kick(reason="Did not complete onboarding within 24 hours.")
                    except disnake.Forbidden:
                        logging.error(f"Failed to kick {member.display_name}: Missing permissions.")
                    except disnake.HTTPException as e:
                        logging.error(f"Failed to kick {member.display_name}: {e}")

    @commands.slash_command(name="clear_member_roles", description="Clears specified roles from all members, preserving certain roles.")
    @commands.has_permissions(administrator=True)
    async def clear_member_roles(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        guild = inter.guild
        if not guild:
            await inter.edit_original_response("Command must be used in a server.")
            return
        if not self.role_clear_target_ids:
            logging.warning("Role clear: No roles specified in ROLE_CLEAR_TARGET_IDS. No roles will be targeted for removal.")
            await inter.edit_original_response("No roles are targeted for removal. Please configure ROLE_CLEAR_TARGET_IDS in the bot's config.")
            return
        target_role_ids_set = set(self.role_clear_target_ids)
        actually_targeted_roles_in_guild = [guild.get_role(r_id) for r_id in self.role_clear_target_ids if guild.get_role(r_id)]
        cleared_count = 0
        member_count = 0
        roles_removed_summary = {}
        tadpole_role_id_int = int(self.tadpole_role_id) if isinstance(self.tadpole_role_id, (int, str)) and str(self.tadpole_role_id).isdigit() else 0

        for member in guild.members:
            if member.bot:
                continue
            member_count += 1
            member_role_ids = {role.id for role in member.roles}
            if tadpole_role_id_int != 0 and tadpole_role_id_int in member_role_ids:
                logging.info(f"Skipping role clear for member {member.display_name} because they have the Tadpole role.")
                continue
            roles_to_remove_for_this_member = []
            for role in member.roles:
                if role.id in target_role_ids_set:
                    if role.is_default():
                        continue 
                    if role.managed:
                        logging.info(f"Skipping managed role {role.name} (ID: {role.id}) for member {member.display_name}, even though it was targeted.")
                        continue
                    if guild.me.top_role <= role:
                        logging.warning(f"Cannot remove role {role.name} (ID: {role.id}) from {member.display_name} due to hierarchy, even though it was targeted.")
                        continue
                    roles_to_remove_for_this_member.append(role)
            if roles_to_remove_for_this_member:
                try:
                    await member.remove_roles(*roles_to_remove_for_this_member, reason="Admin triggered targeted role clear.")
                    cleared_count += 1
                    for r in roles_to_remove_for_this_member:
                        roles_removed_summary[r.name] = roles_removed_summary.get(r.name, 0) + 1
                    logging.info(f"Targeted roles removed from {member.display_name}: {[r.name for r in roles_to_remove_for_this_member]}")
                except disnake.Forbidden:
                    logging.error(f"Failed to remove targeted roles from {member.display_name}: Missing permissions or hierarchy issue.")
                except disnake.HTTPException as e:
                    logging.error(f"Failed to remove targeted roles from {member.display_name}: {e}")
            await asyncio.sleep(0.1)
        response_message = (f"Targeted role clear process finished. Checked {member_count} members. "
                            f"At least one targeted role removed from {cleared_count} members (excluding bots).\n"
                            f"Targeted roles specified in config: {', '.join([r.name for r in actually_targeted_roles_in_guild if r]) or 'None found in guild'}.\n"
                            f"Summary of roles removed: {roles_removed_summary if roles_removed_summary else 'No targeted roles were found on members or could be removed.'}")
        await inter.edit_original_response(response_message)

    @tasks.loop(hours=1)
    async def deadline_kick_task(self):
        await self.bot.wait_until_ready()
        now_utc = datetime.now(timezone.utc)
        if now_utc >= DEADLINE_KICK_DATETIME:
            logging.info(f"Deadline {DEADLINE_KICK_DATETIME} reached. Starting existing user audit.")
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if not guild:
                logging.error("Deadline kick: Guild not found.")
                self.deadline_kick_task.stop()
                return
            if not self.tadpole_role_id:
                logging.error("Deadline kick: Tadpole role ID not configured. Aborting.")
                self.deadline_kick_task.stop()
                return
            join_cutoff = now_utc - timedelta(hours=24)
            kicked_count = 0
            for member in list(guild.members):
                if member.bot:
                    continue
                joined_at_utc = member.joined_at.astimezone(timezone.utc) if member.joined_at else now_utc
                if joined_at_utc < join_cutoff:
                    has_tadpole_role = any(role.id == self.tadpole_role_id for role in member.roles)
                    if not has_tadpole_role:
                        logging.info(f"Deadline kick: Kicking member {member.id} ({member.display_name}) for not having Tadpole role.")
                        try:
                            await member.kick(reason=f"Did not complete onboarding by the {DEADLINE_KICK_DATETIME.strftime('%Y-%m-%d')} deadline.")
                            kicked_count += 1
                        except disnake.Forbidden:
                            logging.error(f"Deadline kick: Failed to kick {member.display_name}: Missing permissions.")
                        except disnake.HTTPException as e:
                            logging.error(f"Deadline kick: Failed to kick {member.display_name}: {e}")
                        await asyncio.sleep(0.1)
            logging.info(f"Deadline kick task finished. Kicked {kicked_count} members.")
            self.deadline_kick_task.stop()

    @commands.slash_command(
        name="toggle_onboarding_kick",
        description="Enables or disables the 24-hour kick for users who haven't completed onboarding."
    )
    @is_admin_or_privileged(user_id=CONFIG['ADMIN_USER_ID'])
    async def toggle_onboarding_kick(self, inter: disnake.ApplicationCommandInteraction, enabled: bool):
        await inter.response.defer(ephemeral=True)
        current_config = Config(CONFIG['CONFIG_FILE'])
        config_data = current_config.read()
        config_data['ENABLE_24H_ONBOARDING_KICK'] = enabled
        self.enable_24h_onboarding_kick = enabled
        message = ""
        if enabled:
            now = datetime.now(timezone.utc)
            next_midnight_utc = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now >= next_midnight_utc:
                next_midnight_utc += timedelta(days=1)
            activation_timestamp_float = next_midnight_utc.timestamp()
            config_data['ONBOARDING_KICK_ACTIVATION_TIMESTAMP'] = activation_timestamp_float
            self.onboarding_kick_activation_timestamp = next_midnight_utc
            self.onboarding_kick_activation_timestamp_float = activation_timestamp_float
            activation_time_str = next_midnight_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
            message_suffix = f"The 24-hour onboarding kick rule for NEW members will become active starting {activation_time_str}."
            logging.info(f"24h onboarding kick activation timestamp set to: {next_midnight_utc}")
            if not self.check_pending_onboarding_task.is_running():
                if not self.tadpole_role_id:
                    message = ("24-hour onboarding kick feature set to ENABLED, but Tadpole Role ID is not configured. "
                               "The task will not run effectively. Please configure it.")
                    logging.warning(message)
                else:
                    self.check_pending_onboarding_task.start()
                    message = f"24-hour onboarding kick feature ENABLED. {message_suffix} The task has been started."
                    logging.info("24h onboarding kick task started by toggle command.")
            else:
                message = f"24-hour onboarding kick feature is already ENABLED and the task is running. {message_suffix}"
        else:
            config_data['ONBOARDING_KICK_ACTIVATION_TIMESTAMP'] = 0.0
            self.onboarding_kick_activation_timestamp = None
            self.onboarding_kick_activation_timestamp_float = 0.0
            if self.check_pending_onboarding_task.is_running():
                self.check_pending_onboarding_task.cancel()
                message = "24-hour onboarding kick feature DISABLED. The task has been stopped."
                logging.info("24h onboarding kick task stopped by toggle command.")
            else:
                message = "24-hour onboarding kick feature is already DISABLED and the task is not running."
        current_config.write(config_data)
        await inter.edit_original_response(content=message)

    @check_pending_onboarding_task.before_loop
    @deadline_kick_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()
        if not self.tadpole_role_id:
            logging.error("Aborting onboarding/audit tasks: Tadpole Role ID is not configured.")
            if self.check_pending_onboarding_task.is_running():
                self.check_pending_onboarding_task.cancel()
            if self.deadline_kick_task.is_running():
                self.deadline_kick_task.cancel()

def setup(bot: commands.Bot):
    bot.add_cog(OnboardingAuditCog(bot))
    logging.info("OnboardingAuditCog has been loaded.") 