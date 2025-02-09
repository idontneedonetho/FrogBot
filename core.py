# core

from typing import Optional, Tuple, Any
from disnake.ext import commands
from pathlib import Path
import importlib.util
import subprocess
import logging
import asyncio
import disnake
import yaml
import sys

CONFIG = {
    'VERSION': 'v3.0',
    'CONFIG_FILE': Path('config.yaml'),
    'COGS_DIR': Path("modules"),
    'TEST_GUILDS': [698205243103641711, 1137853399715549214],
    'ADMIN_USER_ID': 126123710435295232,
}

class Config:
    DEFAULT_FIELDS = {
        'DISCORD_TOKEN': ('Enter your Discord bot token: ', True),
        'DATABASE_FILE': ('Enter your database filename (optional): ', False),
        'OPENAI_API_KEY': ('Enter your OpenAI API key (optional): ', False),
        'GITHUB_TOKEN': ('Enter your GitHub personal access token (optional): ', False)
    }

    def __init__(self, filename: Path = CONFIG['CONFIG_FILE']):
        self._config_path = Path(filename)
        
    def read(self) -> dict[str, Any]: 
        return yaml.safe_load(self._config_path.read_text()) if self._config_path.exists() else {}
    
    def write(self, config: dict[str, Any]) -> None:
        self._config_path.write_text(yaml.safe_dump(config))
    def update(self, key: str, value: Any): self.write({**self.read(), key: value})

    def setup_config(self):
        if self._config_path.exists(): return
        config_data = {}
        for field, (prompt, required) in self.DEFAULT_FIELDS.items():
            if value := input(f"\n{prompt}" if not required else prompt).strip():
                config_data[field] = f"{value}.db" if field == 'DATABASE_FILE' and not value.endswith('.db') else value
            elif required:
                print(f"{field} is required. Please enter a value.")
                return self.setup_config()
        base_dir = Path(__file__).parent
        for dir_path in ["modules", "utils", "logs"]:
            (base_dir / dir_path).mkdir(exist_ok=True)
        (base_dir / "modules" / "__init__.py").touch()
        self.write(config_data)

config = Config()

class GitManager:
    @staticmethod
    async def run_cmd(*args) -> Tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout.decode().strip(), stderr.decode().strip()
        except Exception as e:
            return -1, "", str(e)

    @staticmethod
    async def get_current_branch() -> str:
        try:
            code, stdout, stderr = await GitManager.run_cmd("git", "rev-parse", "--abbrev-ref", "HEAD")
            if code != 0:
                return "beta"
            return stdout.strip() or "beta"
        except Exception as e:
            return "beta"
        
    @staticmethod
    def get_version() -> str:
        try:
            branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()[:7]
            return f"{CONFIG['VERSION']} {branch} {commit}"
        except subprocess.CalledProcessError:
            return f"{CONFIG['VERSION']}-unknown"

    @staticmethod
    async def get_branches() -> list[str]:
        try:
            code, stdout, stderr = await GitManager.run_cmd("git", "branch", "-r")
            if code != 0:
                return ["beta"]
            branches = [b.strip().replace('origin/', '') for b in stdout.split('\n') if 'HEAD' not in b]
            return sorted(branches) if branches else ["beta"]
        except Exception:
            return ["beta"]


class BotManager:
    def __init__(self, client: commands.Bot):
        self.client = client

    async def restart_bot(self, inter: disnake.MessageInteraction) -> None:
        try:
            config.update('restart_channel_id', str(inter.channel.id))
            if inter.message:
                config.update('restart_message_id', str(inter.message.id))
            if not inter.response.is_done():
                await inter.response.edit_message(content="Restarting...")
            else:
                await inter.edit_original_message(content="Restarting...")
            subprocess.Popen([sys.executable, str(Path(__file__).resolve())])
            await self.client.close()
        except Exception as e:
            error_msg = f"Error restarting: {e}"
            if not inter.response.is_done():
                await inter.response.send_message(content=error_msg)
            else:
                await inter.edit_original_message(content=error_msg)
            logging.error(f"Restart error: {e}")

    async def update_bot(self, ctx: commands.Context, branch: str) -> None:
        try:
            code, _, stderr = await GitManager.run_cmd("git", "pull", "-f", "origin", branch)
            if code != 0:
                raise Exception(f"Git pull failed: {stderr}")
            for cog in list(self.client.cogs.keys()):
                self.client.remove_cog(cog)
            ModuleLoader.load_all_modules(self.client)
            await ctx.edit_original_response(content='Update complete.')
        except Exception as e:
            await ctx.edit_original_response(content=f"Update error: {e}")
            logging.error(f"Update error: {e}")
            raise

    async def handle_restart_message(self):
        try:
            config_data = config.read()
            if (channel_id := config_data.get('restart_channel_id')) and (message_id := config_data.get('restart_message_id')):
                if channel := self.client.get_channel(int(channel_id)):
                    try: 
                        message = await channel.fetch_message(int(message_id))
                        await message.edit(content="I'm back online!")
                    except disnake.NotFound: 
                        await channel.send("I'm back online!")
            config.update('restart_channel_id', '')
            config.update('restart_message_id', '')
        except Exception as e: 
            logging.error(f"Error handling restart message: {e}")

def is_admin_or_privileged(user_id: Optional[int] = None, rank_id: Optional[int] = None):
    async def predicate(ctx):
        return (
            ctx.author.guild_permissions.administrator or
            (user_id and ctx.author.id == user_id) or
            (rank_id and any(role.id == rank_id for role in ctx.author.roles))
        )
    return commands.check(predicate)

intents = disnake.Intents.default()
intents.members = intents.messages = intents.message_content = intents.guild_messages = intents.reactions = True
client = commands.Bot(
    command_prefix='//||',
    intents=intents,
    command_sync_flags=commands.CommandSyncFlags.default(),
    test_guilds=CONFIG['TEST_GUILDS']
)
bot_manager = BotManager(client)

class ModuleLoader:
    @staticmethod
    def get_available_modules(cogs_dir: Path = CONFIG['COGS_DIR']) -> dict[str, bool]:
        modules = {}
        cogs_path = Path(cogs_dir)
        if not cogs_path.exists():
            cogs_path.mkdir(parents=True)
            (cogs_path / "__init__.py").touch()
        for file_path in cogs_path.rglob("*.py"):
            if file_path.stem == "__init__": continue
            relative_parts = file_path.relative_to(cogs_dir).parts
            module_name = (
                f"modules.{'.'.join(relative_parts[:-1])}.{file_path.stem}" 
                if len(relative_parts) > 1 
                else f"modules.{file_path.stem}"
            )
            modules[module_name] = True
        return modules

    @staticmethod
    def get_server_modules(guild_id: int) -> list[str]:
        cfg = config.read()
        server_modules = cfg.get('server_modules', {}).get(str(guild_id))
        if server_modules is None:  
            server_modules = list(ModuleLoader.get_available_modules().keys())
            ModuleLoader.set_server_modules(guild_id, server_modules)
        elif server_modules == []:
            return []
        return server_modules

    @staticmethod 
    def set_server_modules(guild_id: int, modules: list[str]):
        cfg = config.read()
        if 'server_modules' not in cfg:
            cfg['server_modules'] = {}
        cfg['server_modules'][str(guild_id)] = modules
        config.write(cfg)

    @staticmethod
    def is_module_enabled(guild_id: int, module_name: str) -> bool:
        return module_name in ModuleLoader.get_server_modules(guild_id)

    @staticmethod
    def get_guild_command_sync_flags(guild_id: int) -> commands.CommandSyncFlags:
        enabled_modules = ModuleLoader.get_server_modules(guild_id)
        if not enabled_modules:
            return commands.CommandSyncFlags.none()
        return commands.CommandSyncFlags.default()

    @classmethod
    def load_all_modules(cls, client: commands.Bot, cogs_dir: Path = CONFIG['COGS_DIR']) -> None:
        guild_modules = {}
        for guild in client.guilds:
            enabled_modules = cls.get_server_modules(guild.id)
            if enabled_modules:
                guild_modules[guild.id] = enabled_modules
        for file_path in Path(cogs_dir).rglob("*.py"):
            if file_path.stem == "__init__": continue
            relative_parts = file_path.relative_to(cogs_dir).parts
            module_name = (
                f"modules.{'.'.join(relative_parts[:-1])}.{file_path.stem}" 
                if len(relative_parts) > 1 
                else f"modules.{file_path.stem}"
            )
            target_guilds = [
                guild_id for guild_id, modules in guild_modules.items()
                if module_name in modules
            ]
            if target_guilds:
                cls.load_single_module(client, file_path, module_name, target_guilds)

    @staticmethod
    def load_single_module(client: commands.Bot, file_path: Path, name: str, target_guilds: list[int]) -> None:
        try:
            spec = importlib.util.spec_from_file_location(name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Failed to load spec for {name}")
            module = importlib.util.module_from_spec(spec)
            module.GUILD_IDS = target_guilds
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            except Exception as e:
                del sys.modules[name]
                raise e
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, commands.Cog) and attr is not commands.Cog:
                    cog = attr(client)
                    for cmd in cog.walk_commands():
                        cmd.guild_ids = target_guilds
                    if hasattr(cog, 'listeners') and callable(getattr(cog, 'listeners')):
                        original_listeners = cog.listeners()
                        cog._listeners = {}
                        for event_name, old_listener in original_listeners:
                            async def wrapped_listener(event_args, old_listener=old_listener):
                                if hasattr(event_args, 'guild') and event_args.guild:
                                    if event_args.guild.id not in target_guilds:
                                        return
                                elif hasattr(event_args, 'guild_id'):
                                    if event_args.guild_id not in target_guilds:
                                        return
                                await old_listener(event_args)
                            cog.add_listener(wrapped_listener, event_name)
                    client.add_cog(cog)
        except Exception as e:
            if name in sys.modules:
                del sys.modules[name]
            logging.error(f"Error loading module {name}: {e}", exc_info=True)

class ModuleListView(disnake.ui.View):
    def __init__(self, guild_id: int = None):
        super().__init__(timeout=300)
        self.current_page = 0
        self.modules_per_page = 9
        self.modules = {}
        self.selected_modules = {}
        self.guild_id = guild_id
        self.add_navigation_buttons()

    def add_navigation_buttons(self):
        nav_buttons = [
            ("◀", "prev_page", disnake.ButtonStyle.secondary),
            ("▶", "next_page", disnake.ButtonStyle.secondary),
            ("Back", "module_list_back", disnake.ButtonStyle.danger),
            ("Apply", "apply_modules", disnake.ButtonStyle.success)
        ]
        for button in nav_buttons:
            self.add_item(disnake.ui.Button(
                label=button[0],
                custom_id=button[1],
                style=button[2],
                row=3
            ))

    async def refresh_module_buttons(self, inter: disnake.MessageInteraction):
        self.clear_items()
        self.add_navigation_buttons()
        if not self.modules:
            current_modules = ModuleLoader.get_available_modules()
            enabled_modules = ModuleLoader.get_server_modules(self.guild_id) if self.guild_id else []
            for module_name in current_modules:
                self.modules[module_name] = {
                    "id": module_name,
                    "installed": True
                }
                if module_name not in self.selected_modules:
                    self.selected_modules[module_name] = module_name in enabled_modules if self.guild_id else True
        total_pages = (len(self.modules) - 1) // self.modules_per_page + 1
        for child in self.children:
            if child.custom_id == "prev_page":
                child.disabled = self.current_page <= 0
            elif child.custom_id == "next_page":
                child.disabled = self.current_page >= total_pages - 1
        start_idx = self.current_page * self.modules_per_page
        page_modules = list(self.modules.items())[start_idx:start_idx + self.modules_per_page]
        for idx, (module_name, info) in enumerate(page_modules):
            row = idx // 3
            if row >= 3:
                continue
            display_name = module_name.split('.')[-1]
            self.add_item(disnake.ui.Button(
                label=display_name,
                style=disnake.ButtonStyle.green if self.selected_modules[module_name] else disnake.ButtonStyle.gray,
                custom_id=f"toggle_module_{module_name}",
                emoji="✅" if self.selected_modules[module_name] else "❌",
                row=row
            ))
        content = f"🧩 Module Manager - {'Server Specific ' if self.guild_id else ''}Page {self.current_page + 1}/{total_pages}"
        if not inter.response.is_done():
            await inter.response.edit_message(content=content, view=self)
        else:
            await inter.edit_original_message(content=content, view=self)

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        try:
            if inter.component.custom_id == "prev_page":
                self.current_page = max(0, self.current_page - 1)
                await self.refresh_module_buttons(inter)
            elif inter.component.custom_id == "next_page":
                total_pages = (len(self.modules) - 1) // self.modules_per_page + 1
                self.current_page = min(total_pages - 1, self.current_page + 1)
                await self.refresh_module_buttons(inter)
            elif inter.component.custom_id == "module_list_back":
                await inter.response.edit_message(
                    content=f"🤖 {client.user.display_name} Control Panel",
                    view=ControlPanelView(guild_id=self.guild_id)
                )
            elif inter.component.custom_id == "apply_modules":
                await inter.response.edit_message(
                    content="Applying changes...",
                    view=None
                )
                if self.guild_id:
                    enabled_modules = [
                        module_name for module_name, info in self.modules.items()
                        if self.selected_modules[module_name]
                    ]
                    ModuleLoader.set_server_modules(self.guild_id, enabled_modules)
                for cog in list(client.cogs.keys()):
                    client.remove_cog(cog)
                for module_name in list(sys.modules):
                    if module_name.startswith('modules.'):
                        del sys.modules[module_name]
                ModuleLoader.load_all_modules(client)
                await inter.edit_original_message(
                    content=f"{'Server modules' if self.guild_id else 'Modules'} updated successfully!",
                    view=None
                )
            elif inter.component.custom_id.startswith("toggle_module_"):
                module_name = inter.component.custom_id.replace("toggle_module_", "")
                self.selected_modules[module_name] = not self.selected_modules[module_name]
                await self.refresh_module_buttons(inter)
            return True
        except Exception as e:
            if not inter.response.is_done():
                await inter.response.send_message(content=f"An error occurred: {str(e)}", ephemeral=True)
            logging.error(f"Error in ModuleListView interaction: {e}")
            return False

class BranchSelect(disnake.ui.Select):
    def __init__(self, branches: list[str]):
        options = [
            disnake.SelectOption(
                label=branch,
                default=(branch == "beta")
            ) 
            for branch in branches
        ]
        super().__init__(
            placeholder="Select branch",
            options=options,
            min_values=1,
            max_values=1
        )

class UpdateView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.branch = "beta"
        self.add_item(disnake.ui.Button(
            label="Back",
            style=disnake.ButtonStyle.danger,
            custom_id="update_view_back"
        ))
        self.add_item(disnake.ui.Button(
            label="Update & Restart",
            style=disnake.ButtonStyle.success,
            custom_id="update_and_restart",
            emoji="🔄"
        ))

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        try:
            if inter.component.custom_id == "update_view_back":
                await inter.response.edit_message(
                    content=f"🤖 {client.user.display_name} Control Panel",
                    view=ControlPanelView()
                )
            elif inter.component.custom_id == "update_and_restart":
                await inter.response.edit_message(content="Updating and restarting...", view=None)
                try:
                    await bot_manager.update_bot(inter, self.branch)
                    await bot_manager.restart_bot(inter)
                except Exception as e:
                    await inter.edit_original_message(content=f"Error during update: {e}")
            elif inter.component.type == disnake.ComponentType.select:
                self.branch = inter.values[0]
                await inter.response.edit_message(
                    content=f"Selected branch: {self.branch}",
                    view=self
                )
            return True
        except Exception as e:
            logging.error(f"Error in UpdateView interaction: {e}")
            if not inter.response.is_done():
                await inter.response.send_message(content=f"An error occurred: {str(e)}")
            return False

class ControlPanelView(disnake.ui.View):
    def __init__(self, guild_id: int = None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        BUTTONS = [
            ("Update Bot", disnake.ButtonStyle.success, "panel_update", "⬆️"),
            ("Modules", disnake.ButtonStyle.primary, "panel_modules", "🧩"),
            ("Restart Bot", disnake.ButtonStyle.secondary, "panel_restart", "🔄"),
            ("Shutdown", disnake.ButtonStyle.danger, "panel_shutdown", "⛔")
        ]
        for label, style, cid, emoji in BUTTONS:
            self.add_item(disnake.ui.Button(
                label=label,
                style=style,
                custom_id=cid,
                emoji=emoji
            ))

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        try:
            handlers = {
                "panel_update": self.show_update_options,
                "panel_modules": self.show_module_options,
                "panel_restart": self.confirm_restart,
                "panel_shutdown": self.confirm_shutdown
            }
            cid = inter.component.custom_id
            if handler := handlers.get(cid):
                await handler(inter)
            return True
        except Exception as e:
            if not inter.response.is_done():
                await inter.response.edit_message(content=f"An error occurred: {str(e)}")
            logging.error(f"Error in ControlPanelView interaction: {e}")
            return False

    async def show_update_options(self, inter: disnake.MessageInteraction):
        update_view = UpdateView()
        branches = await GitManager.get_branches()
        if branches:
            update_view.add_item(BranchSelect(branches))
        await inter.response.edit_message(
            content="⬆️ Update Options (default: beta)",
            view=update_view
        )

    async def show_module_options(self, inter: disnake.MessageInteraction):
        try:
            module_view = ModuleListView(guild_id=self.guild_id)
            await module_view.refresh_module_buttons(inter)
        except Exception as e:
            if not inter.response.is_done():
                await inter.response.send_message(
                    content=f"An error occurred: {str(e)}",
                    ephemeral=True
                )
            logging.error(f"Error in show_module_options: {e}")

    async def show_server_module_options(self, inter: disnake.MessageInteraction):
        try:
            module_view = ModuleListView(guild_id=self.guild_id)
            await module_view.refresh_module_buttons(inter)
        except Exception as e:
            if not inter.response.is_done():
                await inter.response.send_message(
                    content=f"An error occurred: {str(e)}",
                    ephemeral=True
                )
            logging.error(f"Error in show_server_module_options: {e}")

    async def confirm_restart(self, inter: disnake.MessageInteraction):
        class ConfirmView(disnake.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(disnake.ui.Button(label="Confirm Restart", style=disnake.ButtonStyle.danger, custom_id="confirm_restart_yes", emoji="✅"))
                self.add_item(disnake.ui.Button(label="Cancel", style=disnake.ButtonStyle.secondary, custom_id="confirm_restart_no", emoji="❌"))

            async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
                try:
                    if inter.component.custom_id == "confirm_restart_yes":
                        await inter.response.edit_message(content="Restarting...", view=None)
                        await bot_manager.restart_bot(inter)
                    else:
                        await inter.response.edit_message(content=f"🤖 {client.user.display_name} Control Panel", view=ControlPanelView())
                    return True
                except Exception as e:
                    if not inter.response.is_done():
                        await inter.response.send_message(content=f"An error occurred: {str(e)}", ephemeral=True)
                    logging.error(f"Error in ConfirmView interaction: {e}")
                    return False
        await inter.response.edit_message(content=f"⚠️ Are you sure you want to restart {client.user.display_name}?", view=ConfirmView())

    async def confirm_shutdown(self, inter: disnake.MessageInteraction):
        class ConfirmView(disnake.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                self.add_item(disnake.ui.Button(label="Confirm Shutdown", style=disnake.ButtonStyle.danger, custom_id="confirm_shutdown_yes", emoji="✅"))
                self.add_item(disnake.ui.Button(label="Cancel", style=disnake.ButtonStyle.secondary, custom_id="confirm_shutdown_no", emoji="❌"))

            async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
                if inter.component.custom_id == "confirm_shutdown_yes":
                    await inter.response.edit_message(content="Shutting down...", view=None)
                    await client.close()
                else:
                    await inter.response.edit_message(content=f"🤖 {client.user.display_name} Control Panel", view=ControlPanelView())
                return True
        await inter.response.edit_message(content=f"⚠️ Are you sure you want to shut down {client.user.display_name}?", view=ConfirmView())

@client.slash_command(name="control_panel", description="Open the bot's control panel")
@is_admin_or_privileged(user_id=CONFIG['ADMIN_USER_ID'])
async def control_panel(ctx): 
    guild_id = ctx.guild.id if ctx.guild else None
    await ctx.send(
        f"🤖 {client.user.display_name} Control Panel",
        view=ControlPanelView(guild_id=guild_id),
        ephemeral=True
    )

@client.event
async def on_ready():
    await client.change_presence(activity=disnake.Game(name=f"/help | {GitManager.get_version()}"))
    print(f'Logged in as {client.user.name}')
    for cog in list(client.cogs.keys()):
        client.remove_cog(cog)
    for module_name in list(sys.modules):
        if module_name.startswith('modules.'):
            del sys.modules[module_name]
    ModuleLoader.load_all_modules(client)
    await bot_manager.handle_restart_message()

def main():
    try:
        logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
        config.setup_config()
        if not (token := config.read().get('DISCORD_TOKEN')): 
            raise ValueError("Discord token not found in config")
        if db_file := config.read().get('DATABASE_FILE'): 
            Path(db_file).touch(exist_ok=True)
        client.run(token)
    except KeyboardInterrupt: 
        print("\nSetup cancelled. Please run the bot again to complete setup.")
        sys.exit(1)
    except Exception as e: 
        print(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == "__main__": main()