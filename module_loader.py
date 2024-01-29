# module_loader.py
import importlib.util
import os

class ModuleLoader:
    def __init__(self, directory):
        self.directory = directory
        self.modules = []

    def load_modules(self, bot):
        for filename in os.listdir(self.directory):
            if filename.endswith('.py'):
                module_name = filename[:-3]
                module_path = os.path.join(self.directory, filename)
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self.modules.append(module)
                print(f"Loading module: {module_name}")
                if hasattr(module, 'setup'):
                    module.setup(bot)

    def get_command_handlers(self):
        handlers = {}
        for module in self.modules:
            if hasattr(module, 'cmd'):
                for command, handler_name in module.cmd.items():
                    if hasattr(module, handler_name):
                        handlers[command] = getattr(module, handler_name)
        return handlers

    def get_event_handlers(self, event_name):
        handlers = []
        for module in self.modules:
            if hasattr(module, event_name):
                handlers.append(getattr(module, event_name))
        return handlers