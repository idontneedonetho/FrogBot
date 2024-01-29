from discord.ext import commands
from modules.utils.commons import is_admin
from module_loader import ModuleLoader

class ReloadCommand:
    def __init__(self, directory):
        self.loader = ModuleLoader(directory)

    async def reload_module(self, ctx, module_name):
        self.loader.modules = [m for m in self.loader.modules if m.__name__ != module_name]
        module = self.loader.load_module(ctx.bot, module_name)
        if module is None:
            await ctx.reply(f"Module {module_name} does not exist.")
            return
        await ctx.reply(f"Reloaded module: {module_name}")
        if hasattr(module, 'setup'):
            module.setup(ctx.bot)

def setup(client):
    reload_command = ReloadCommand('modules')
    @commands.command(name="reload")
    async def reload(ctx, module_name):
        await reload_command.reload_module(ctx, module_name)
    client.add_command(reload)