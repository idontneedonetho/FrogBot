# modules.agent_search

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.google_genai import GoogleGenAI
from modules.utils.commons import send_long_message
from disnake import ApplicationCommandInteraction
from llama_index.core.tools import FunctionTool
from llama_index.core import Settings
from disnake.ext import commands
from google.genai import types
from typing import Optional
from core import config
import subprocess
import shlex
import glob
import os

class CodeSearchTools:
    def __init__(self, search_path: str):
        self.search_path = search_path
    
    async def execute_ripgrep(self, command_args: str, explanation: str = "") -> str:
        rg_cmd = ["rg", "-n"] + shlex.split(command_args)
        if '.' in rg_cmd:
            dot_index = rg_cmd.index('.')
            rg_cmd[dot_index] = self.search_path
        else:
            rg_cmd.append(self.search_path)
        try:
            result = subprocess.run(
                rg_cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            if result.returncode == 0 and result.stdout and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                limited_lines = lines[:50]
                results = [f"Search: {explanation or 'Custom ripgrep search'}"]
                results.append(f"Command: rg {command_args}")
                results.append("")
                for line in limited_lines:
                    results.append(line)
                total_matches = len(lines)
                if total_matches > 50:
                    results.append(f"\n... (showing first 50 of {total_matches} total matches)")
                results.append(f"\nFound {total_matches} matches")
                final_result = '\n'.join(results)
                return final_result
            else:
                no_result = f"No matches found.\nCommand: rg {command_args}\nSearch path: {self.search_path}"
                if result.stderr:
                    no_result += f"\nError: {result.stderr}"
                return no_result
        except subprocess.TimeoutExpired:
            return f"Search timed out after 30 seconds. Command: rg {command_args}"
        except Exception as e:
            return f"Search failed with error: {str(e)}. Command: rg {command_args}"

    async def list_directory(self, directory_path: str = ".", include_hidden: bool = False, 
                           recursive: bool = False, file_types: Optional[str] = None) -> str:
        if os.path.isabs(directory_path):
            full_path = directory_path
        else:
            full_path = os.path.join(self.search_path, directory_path)
        if not os.path.exists(full_path):
            return f"Directory not found: {directory_path}"
        if not os.path.isdir(full_path):
            return f"Path is not a directory: {directory_path}"
        results = [f"Directory listing: {directory_path}"]
        results.append("=" * 50)
        if recursive:
            for root, dirs, files in os.walk(full_path):
                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                rel_root = os.path.relpath(root, full_path)
                if rel_root == '.':
                    rel_root = ''
                if rel_root:
                    results.append(f"\n📁 {rel_root}/")
                for file in sorted(files):
                    if not include_hidden and file.startswith('.'):
                        continue
                    if file_types:
                        extensions = [ext.strip().lstrip('*.') for ext in file_types.split(',')]
                        file_ext = file.split('.')[-1] if '.' in file else ''
                        if file_ext not in extensions:
                            continue
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        if rel_root:
                            results.append(f"  📄 {file} ({size} bytes)")
                        else:
                            results.append(f"📄 {file} ({size} bytes)")
                    except OSError:
                        if rel_root:
                            results.append(f"  📄 {file} (size unknown)")
                        else:
                            results.append(f"📄 {file} (size unknown)")
        else:
            try:
                items = sorted(os.listdir(full_path))
                for item in items:
                    if not include_hidden and item.startswith('.'):
                        continue
                    item_path = os.path.join(full_path, item)
                    if os.path.isdir(item_path):
                        results.append(f"📁 {item}/")
                    else:
                        if file_types:
                            extensions = [ext.strip().lstrip('*.') for ext in file_types.split(',')]
                            file_ext = item.split('.')[-1] if '.' in item else ''
                            if file_ext not in extensions:
                                continue
                        try:
                            size = os.path.getsize(item_path)
                            results.append(f"📄 {item} ({size} bytes)")
                        except OSError:
                            results.append(f"📄 {item} (size unknown)")
            except PermissionError:
                return f"Permission denied accessing directory: {directory_path}"
        total_items = len([r for r in results[2:] if r.strip() and not r.startswith('\n📁')])
        results.append(f"\nTotal items: {total_items}")
        return '\n'.join(results)

    async def glob_search(self, pattern: str, recursive: bool = True) -> str:
        search_pattern = os.path.join(self.search_path, pattern)
        if recursive:
            matches = glob.glob(search_pattern, recursive=True)
        else:
            matches = glob.glob(search_pattern)
        relative_matches = []
        for match in sorted(matches):
            try:
                rel_path = os.path.relpath(match, self.search_path)
                if os.path.isfile(match):
                    size = os.path.getsize(match)
                    relative_matches.append(f"📄 {rel_path} ({size} bytes)")
                else:
                    relative_matches.append(f"📁 {rel_path}/")
            except OSError:
                rel_path = os.path.relpath(match, self.search_path)
                relative_matches.append(f"❓ {rel_path} (unknown)")
        if relative_matches:
            results = [f"Glob search results for: {pattern}"]
            results.append("=" * 50)
            results.extend(relative_matches)
            results.append(f"\nFound {len(relative_matches)} matches")
            return '\n'.join(results)
        else:
            return f"No files found matching pattern: {pattern}"

    async def read_file(self, file_path: str, start_line: Optional[int] = None, 
                       end_line: Optional[int] = None, max_lines: int = 300) -> str:
        if os.path.isabs(file_path):
            full_path = file_path
        else:
            full_path = os.path.join(self.search_path, file_path)
        if not os.path.exists(full_path):
            error_msg = f"File not found: {file_path}"
            return error_msg
        if not os.path.isfile(full_path):
            error_msg = f"Path is not a file: {file_path}"
            return error_msg
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            total_lines = len(lines)
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else total_lines
                start_idx = max(0, start_idx)
                end_idx = min(total_lines, end_idx)
                if start_idx >= total_lines:
                    return f"Start line {start_line} exceeds file length ({total_lines} lines)"
                selected_lines = lines[start_idx:end_idx]
                actual_start = start_idx + 1
                actual_end = min(end_idx, total_lines)
                if len(selected_lines) > max_lines:
                    selected_lines = selected_lines[:max_lines]
                    actual_end = actual_start + max_lines - 1
                content = ''.join(selected_lines)
                result = f"File: {file_path} (lines {actual_start}-{actual_end} of {total_lines}):\n"
                result += "=" * 60 + "\n"
                result += content
                if len(lines[start_idx:end_idx]) > max_lines:
                    result += f"\n... (truncated to {max_lines} lines)"
            else:
                if total_lines > max_lines:
                    content = ''.join(lines[:max_lines])
                    result = f"File: {file_path} (first {max_lines} of {total_lines} lines):\n"
                    result += "=" * 60 + "\n"
                    result += content
                    result += f"\n... (truncated to {max_lines} lines)\n"
                    result += "⚠️ Large file! Use start_line/end_line parameters to read specific sections."
                elif total_lines > 50:
                    content = ''.join(lines[:max_lines])
                    result = f"File: {file_path} (first {max_lines} of {total_lines} lines):\n"
                    result += "=" * 60 + "\n"
                    result += content
                    result += f"\n... (showing first {max_lines} lines)\n"
                    result += "💡 Consider using start_line/end_line to read specific sections if you need more."
                else:
                    content = ''.join(lines)
                    result = f"File: {file_path} ({total_lines} lines):\n"
                    result += "=" * 60 + "\n"
                    result += content
            return result
        except UnicodeDecodeError:
            error_msg = f"Cannot read file (binary or encoding issue): {file_path}"
            return error_msg
        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            return error_msg

class AgentSearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        config_data = config.read()
        api_key = config_data.get('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in config.yaml")
        self.search_path = config_data.get('CODE_SEARCH_PATH', '.')
        self.llm = GoogleGenAI(
            model="gemini-2.0-flash",
            api_key=api_key,
            generation_config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_budget=0
                ),
            ),
        )
        Settings.llm = self.llm
        self.tools = CodeSearchTools(self.search_path)
        tool_definitions = [
            (self.tools.execute_ripgrep, "execute_ripgrep", "Execute ripgrep search with advanced filtering and context options"),
            (self.tools.list_directory, "list_directory", "List directory contents with filtering options"),
            (self.tools.glob_search, "glob_search", "Search for files using glob patterns"),
            (self.tools.read_file, "read_file", "Read file contents with optional line ranges. Use this to read specific sections of files."),
        ]
        function_tools = []
        for func, name, desc in tool_definitions:
            tool = FunctionTool.from_defaults(
                fn=func,
                name=name,
                description=desc,
            )
            function_tools.append(tool)
        self.search_agent = FunctionAgent(
            name="CodeAnalysisAgent",
            description="AI-powered code search and analysis agent with focused toolset",
            system_prompt="""You help users understand and use FrogPilot, a fork of OpenPilot. Search thoroughly and give a practical answer.

SEARCH APPROACH:
- Try multiple search terms and patterns until you find relevant code/UI
- Look for UI files, settings, configuration, and user-facing features
- Don't give up after one search - keep digging

RESPONSE STYLE:
- DEFAULT: Assume user wants to USE the software (step-by-step instructions)
- TECHNICAL: Only if they ask about "code", "implementation", or "how it works"
- Focus on what they can actually DO
- NEVER tell the user to 'find' ANYTHING, give them the actual location. Search for the location and give them the steps to get there.

WHEN SEARCHING FOR USER FEATURES:
1. Search for UI elements, settings, menus, buttons
2. Look for configuration files and user preferences  
3. Find the actual implementation to understand how it works
4. Think through the logic: if setting is "Hide X", enabling it hides X
5. Give clear, accurate steps based on what you find

Keep searching until you find the actual answer. Don't give up and suggest they ask elsewhere. You must provide proof of understanding with your response.""",
            tools=function_tools,
            llm=self.llm,
        )

    @commands.slash_command(
        name="agent_search",
        description="AI-powered code search and analysis with focused toolset"
    )
    async def agent_search(
        self, 
        inter: ApplicationCommandInteraction,
        question: str = commands.Param(description="Your question about the codebase")
    ):
        await inter.response.defer()
        try:
            await inter.edit_original_response(content="🔍 AI agent analyzing codebase...")
            response = await self.search_agent.run(question)
            final_answer = str(response)
            await send_long_message(inter.channel, final_answer, should_reply=False)
        except Exception as e:
            await inter.edit_original_response(content=f"❌ Code agent search failed: {str(e)}")

def setup(bot: commands.Bot):
    bot.add_cog(AgentSearchCog(bot))