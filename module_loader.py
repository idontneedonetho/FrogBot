# module_loader

import importlib.util
import os

class ModuleLoader:
    def __init__(self, directory):
        self.directory = directory
        self.modules = []

    def load_modules(self, client):
        for root, dirs, files in os.walk(self.directory):
            if 'utils' in dirs:
                dirs.remove('utils')
            for filename in files:
                if filename.endswith('.py'):
                    module_name = filename[:-3]
                    module_path = os.path.join(root, filename)
                    try:
                        module = self._load_module(module_name, module_path)
                        self.modules.append(module)
                        print(f"Loading module: {module_name}")
                        if hasattr(module, 'setup'):
                            module.setup(client)
                    except Exception as e:
                        print(f"Failed to load module: {module_name}. Error: {e}")

    def _load_module(self, module_name, module_path):
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def get_command_handlers(self):
        return {command: getattr(module, handler_name) 
                for module in self.modules if hasattr(module, 'cmd') 
                for command, handler_name in module.cmd.items() 
                if hasattr(module, handler_name)}

    def get_event_handlers(self, event_name):
        return [getattr(module, event_name) 
                for module in self.modules if hasattr(module, event_name)]