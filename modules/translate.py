# modules.translate

from disnake import Embed, Color, Message, ApplicationCommandInteraction, ModalInteraction, MessageCommandInteraction, TextInputStyle, ui
from google.generativeai.types import GenerationConfig
from modules.utils.commons import send_long_message
from asyncio import Queue, create_task, sleep
from typing import Set, List, Dict, Tuple
import google.generativeai as genai
from modules.utils import database
from disnake.ext import commands
from functools import lru_cache
from core import config
import disnake
import logging
import json

class TranslationConfig:
    MODEL_NAME = "gemini-2.0-flash"
    CONTEXT_MESSAGES = 7
    NUM_WORKERS = 3
    SAFETY_SETTINGS = [
        {"category": cat, "threshold": "BLOCK_NONE"}
        for cat in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", 
                   "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
    ]
    SYSTEM_PROMPT = """You are a translation assistant. Your job is to:
1. Translate messages while maintaining context and nuance
2. Never add commentary or additional messages
3. Always use full language names
4. Never translate into the source language - only translate into the target languages.
5. Return translations ONLY as a valid JSON object containing a single key 'translations', which maps lowercase language names to translated text."""

EXPECTED_RESPONSE_SCHEMA = Dict[str, Dict[str, str]]

genai.configure(api_key=config.read().get('GOOGLE_API_KEY'))
gemini_model = genai.GenerativeModel(TranslationConfig.MODEL_NAME)

class TranslationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.translation_queue = Queue()
        self.worker_tasks: List[create_task] = []
        self.cleanup_task = None
        self._ready = False

    async def cog_load(self):
        if self._ready:
            return
        self._ready = True
        await self.setup_tasks()

    def cog_unload(self):
        if self.cleanup_task:
            self.cleanup_task.cancel()
        for task in self.worker_tasks:
            task.cancel()
        self._ready = False

    async def setup_tasks(self):
        if self.cleanup_task:
            self.cleanup_task.cancel()
        for task in self.worker_tasks:
            task.cancel()
        self.worker_tasks.clear()
        self.worker_tasks.extend(create_task(self.translation_worker()) for _ in range(TranslationConfig.NUM_WORKERS))

    @lru_cache(maxsize=100)
    def _format_language_name(self, lang: str) -> str:
        return ' '.join(word.capitalize() for word in lang.split())

    async def translate_message(self, content: str, target_langs: Set[str], thread_id: int, username: str, user_id: int, message) -> Tuple[str, Dict[str, str]]:
        try:
            if not content.strip():
                return '', {}
            if isinstance(message, Message) and message.mentions:
                content = ' '.join(content.replace(f'<@{m.id}>', m.display_name).replace(f'<@!{m.id}>', m.display_name) 
                                 for m in message.mentions)
            user_lang = await database.get_user_language(thread_id, user_id) or 'english'
            history_messages = await self._get_message_context(message)
            prompt_history = []
            prompt_history.append({"role": "user", "parts": [TranslationConfig.SYSTEM_PROMPT]})
            prompt_history.append({"role": "model", "parts": ["Okay, I will follow these instructions and output only the specified JSON structure."]})
            for msg in history_messages:
                prompt_history.append({"role": "user", "parts": [f"{msg.author.display_name}: {msg.content}"]})
            final_request = f"Translate this message from {self._format_language_name(user_lang)} to {', '.join(self._format_language_name(lang) for lang in target_langs)}:\n{content}"
            prompt_history.append({"role": "user", "parts": [final_request]})
            response_json = await self._make_api_request(prompt_history, target_langs)
            translations = self._parse_translation_response(response_json, content)
            return user_lang, translations
        except Exception as e:
            logging.error(f"Translation error: {e}")
            raise

    async def _get_message_context(self, message) -> List[Message]:
        if not isinstance(message.channel, disnake.Thread):
            return []
        history = [msg async for msg in message.channel.history(limit=TranslationConfig.CONTEXT_MESSAGES, before=message.created_at)
                   if not msg.author.bot and msg.content.strip()]
        return list(reversed(history))

    async def _make_api_request(self, messages: List[dict], target_langs: Set[str]) -> dict:
        try:
            lang_properties = {lang.lower(): {"type": "string"} for lang in target_langs}
            lang_ordering = sorted(list(lang_properties.keys()))
            gen_config = GenerationConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "translations": {
                            "type": "object",
                            "properties": lang_properties,
                            "required": lang_ordering
                        }
                    },
                    "required": ["translations"]
                }
            )
            response = await gemini_model.generate_content_async(
                messages,
                generation_config=gen_config,
                safety_settings=TranslationConfig.SAFETY_SETTINGS,
                request_options={'timeout': 60}
            )
            if not response.text:
                 logging.error("Received empty response text from Gemini API.")
                 raise ValueError("Received empty response from translation model")
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode JSON response: {e}\nResponse text: {getattr(response, 'text', 'N/A')}")
            raise ValueError("Received invalid JSON format from translation model") from e
        except (AttributeError, KeyError, IndexError) as e:
            logging.error(f"Error processing Gemini API response structure: {e}")
            raise ValueError("Error processing response from translation model") from e
        except Exception as e:
            logging.error(f"Google Gemini API error: {e}")
            raise

    def _parse_translation_response(self, response_json: dict, original_content: str) -> Dict[str, str]:
        if not isinstance(response_json, dict) or "translations" not in response_json:
             logging.error(f"Invalid JSON structure received: {response_json}")
             raise ValueError("Invalid JSON structure from translation model")
        translations = response_json.get("translations", {})
        if not isinstance(translations, dict):
            logging.error(f"Expected 'translations' to be a dict, got: {type(translations)}")
            raise ValueError("Invalid 'translations' format in JSON response")
        valid_translations = {}
        for lang, trans in translations.items():
             if isinstance(lang, str) and isinstance(trans, str) and trans.strip() != original_content.strip():
                 valid_translations[lang.lower()] = trans
        return valid_translations
    
    async def translation_worker(self):
        while True:
            try:
                message, content, target_langs, thread_id, username, user_id = await self.translation_queue.get()
                try:
                    if (message.channel.locked or 
                        not await database.is_thread_active(thread_id) or 
                        not content.strip()):
                        continue
                    _, translations = await self.translate_message(
                        content, target_langs, thread_id, username, user_id, message
                    )
                    if translations:
                        response = self._create_translation_embed(content, translations)
                        await send_long_message(message, response, should_reply=True)
                except Exception as e:
                    logging.error(f"Error in translation worker: {e}")
                finally:
                    self.translation_queue.task_done()
            except Exception as e:
                logging.error(f"Translation worker critical error: {e}")
                await sleep(1)

    def _create_translation_embed(self, original_text: str, translations: Dict[str, str], auto: bool = True) -> str:
        parts = []
        if not auto:
            parts.append("Original:\n" + "\n".join(f"> {line}" for line in original_text.split('\n')))
        parts.extend(
            f"**{self._format_language_name(lang)}:**\n" + "\n".join(f"> {line}" for line in text.split('\n'))
            for lang, text in translations.items() if text and text.strip()
        )
        joined_parts = "\n\n".join(parts)
        return f"{joined_parts}\n\n-# ⚠️ These translations were generated by an AI language model and may not be perfectly accurate."

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if (message.author.bot or 
            not isinstance(message.channel, disnake.Thread) or
            not await database.is_thread_active(message.channel.id)):
            return
        thread_languages = await database.get_thread_languages(message.channel.id)
        if not thread_languages:
            return
        await self.translation_queue.put((
            message, 
            message.content, 
            set(thread_languages), 
            message.channel.id, 
            message.author.display_name, 
            message.author.id
        ))

    async def _handle_thread_command(self, inter: ApplicationCommandInteraction, action: str) -> None:
        if not isinstance(inter.channel, disnake.Thread):
            await self._send_embed(inter, "❌ Invalid Channel", "This command can only be used in threads!", Color.red())
            return
        thread_id = inter.channel.id
        is_active = await database.is_thread_active(thread_id)
        if action == "enable":
            if is_active:
                await self._send_embed(inter, "❌ Already Active", "Auto-translation is already enabled in this thread!", Color.red())
                return
            await database.set_thread_active(thread_id, True)
            description = (
                "Auto-translation has been enabled for this thread!\n\n"
                "**How it works**\n"
                "• Messages will be translated based on user language preferences\n"
                "• Set your language preference with `/translate set_language [language]`\n"
                "• Add target languages with `/translate language add [language]`"
            )
            await self._send_embed(inter, "🌐 Translation Enabled", description, Color.green(), ephemeral=False)
        elif action == "disable":
            if not is_active:
                await self._send_embed(inter, "❌ Not Active", "Auto-translation is not enabled in this thread!", Color.red())
                return
            await database.set_thread_active(thread_id, False)
            await self._send_embed(inter, "🌐 Translation Disabled", "Auto-translation has been disabled for this thread.", Color.orange(), ephemeral=False)
        else:
            embed = Embed(
                title="🌐 Translation Status",
                description=f"Auto-translation is currently **{'enabled' if is_active else 'disabled'}** in this thread.",
                color=Color.green() if is_active else Color.red()
            )
            if is_active:
                thread_languages = await database.get_thread_languages(thread_id)
                if thread_languages:
                    embed.add_field(
                        name="Active Languages",
                        value=", ".join(self._format_language_name(lang) for lang in thread_languages),
                        inline=False
                    )
                    embed.add_field(
                        name="Managing Languages",
                        value=(
                            "• Add a language: `/translate language add [language]`\n"
                            "• Remove a language: `/translate language remove [language]`\n"
                            "• Set your language: `/translate set_language [language]`"
                        ),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="No Languages Set",
                        value="Use `/translate language add [language]` to add languages for translation.",
                        inline=False
                    )
            await inter.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(name="translate", description="Translation management commands")
    async def translate_group(self, inter: ApplicationCommandInteraction):
        pass

    @translate_group.sub_command(name="message", description="Translate a message to another language")
    async def translate_message_cmd(self, inter: ApplicationCommandInteraction):
        modal = ui.Modal(
            title="Translate Text",
            custom_id="translate_modal",
            components=[
                ui.TextInput(
                    label="Text to translate",
                    custom_id="text_to_translate",
                    style=TextInputStyle.paragraph,
                    max_length=1000,
                    placeholder="Enter the text you want to translate..."
                ),
                ui.TextInput(
                    label="Target language",
                    custom_id="target_language",
                    style=TextInputStyle.short,
                    max_length=50,
                    placeholder="e.g., Spanish, French, German..."
                )
            ]
        )
        await inter.response.send_modal(modal)

    @translate_group.sub_command(name="thread", description="Manage thread translation settings")
    async def thread_cmd(
        self,
        inter: ApplicationCommandInteraction,
        action: str = commands.Param(choices=["enable", "disable", "status"], description="Action to perform")
    ):
        await self._handle_thread_command(inter, action)

    @translate_group.sub_command(name="set_language", description="Set your preferred language for translations")
    async def set_language_cmd(
        self,
        inter: ApplicationCommandInteraction,
        language: str = commands.Param(description="Your preferred language (e.g., English, Spanish, French)")
    ):
        if not isinstance(inter.channel, disnake.Thread):
            await self._send_embed(inter, "❌ Invalid Channel", "This command can only be used in threads!", Color.red())
            return
        thread_id = inter.channel.id
        if not await database.is_thread_active(thread_id):
            await self._send_embed(inter, "❌ Not Active", "Auto-translation is not enabled in this thread!", Color.red())
            return
        await database.set_user_language(thread_id, inter.author.id, language.lower().strip())
        await self._send_embed(
            inter, 
            "✅ Language Set", 
            f"Your preferred language has been set to {self._format_language_name(language)}.", 
            Color.green(),
            ephemeral=False
        )

    @translate_group.sub_command(name="language", description="Add or remove a language from thread translations")
    async def language_cmd(
        self,
        inter: ApplicationCommandInteraction,
        action: str = commands.Param(choices=["add", "remove"], description="Add or remove a language"),
        language: str = commands.Param(description="Language name (e.g., English, Spanish, French)")
    ):
        if not isinstance(inter.channel, disnake.Thread):
            await self._send_embed(inter, "❌ Invalid Channel", "This command can only be used in threads!", Color.red())
            return
        thread_id = inter.channel.id
        if not await database.is_thread_active(thread_id):
            await self._send_embed(inter, "❌ Not Active", "Auto-translation is not enabled in this thread!", Color.red())
            return
        language = language.lower().strip()
        if action == "add":
            await database.add_thread_language(thread_id, language)
            await self._send_embed(
                inter, 
                "✅ Language Added", 
                f"Added {self._format_language_name(language)} to thread translations.", 
                Color.green(),
                ephemeral=False
            )
        else:
            thread_languages = await database.get_thread_languages(thread_id)
            if language not in thread_languages:
                await self._send_embed(
                    inter, 
                    "❌ Language Not Found", 
                    f"{self._format_language_name(language)} is not in the thread's language list.", 
                    Color.red()
                )
                return
            await database.remove_thread_language(thread_id, language)
            await self._send_embed(
                inter, 
                "🗑️ Language Removed", 
                f"Removed {self._format_language_name(language)} from thread translations.", 
                Color.orange(),
                ephemeral=False
            )

    async def _handle_translation_modal(self, inter: ModalInteraction, message_id: int = None):
        await inter.response.defer()
        target_lang = inter.text_values["target_language"].lower()
        if message_id:
            message = await inter.channel.fetch_message(message_id)
            text_to_translate = message.content
            author_name = message.author.display_name
            author_id = message.author.id
            source = message
        else:
            text_to_translate = inter.text_values["text_to_translate"]
            author_name = inter.author.display_name
            author_id = inter.author.id
            source = inter
        if not text_to_translate.strip():
            await inter.edit_original_response("The selected message has no text to translate.")
            return
        _, translations = await self.translate_message(
            text_to_translate,
            {target_lang},
            inter.channel.id if isinstance(inter.channel, disnake.Thread) else 0,
            author_name,
            author_id,
            source
        )
        if translations:
            response = self._create_translation_embed(text_to_translate, translations, auto=False)
            await inter.edit_original_response(content=response)
        else:
            await inter.edit_original_response("Translation failed or produced no results.")

    @commands.Cog.listener("on_modal_submit")
    async def on_translate_modal_submit(self, inter: ModalInteraction):
        try:
            if inter.custom_id == "translate_modal":
                await self._handle_translation_modal(inter)
            elif inter.custom_id.startswith("context_translate:"):
                message_id = int(inter.custom_id.split(":")[1])
                await self._handle_translation_modal(inter, message_id)
        except Exception as e:
            logging.error(f"Modal translation error: {e}")
            await inter.edit_original_response("Failed to translate message. Please try again later.")

    @commands.message_command(name="Translate")
    async def translate_context_menu(self, inter: MessageCommandInteraction, message: Message):
        if message.author.bot:
            await inter.response.send_message("Cannot translate bot messages.", ephemeral=True)
            return
        if not message.content.strip():
            await inter.response.send_message("The selected message has no text to translate.", ephemeral=True)
            return
        modal = ui.Modal(
            title="Translate Message",
            custom_id=f"context_translate:{message.id}",
            components=[
                ui.TextInput(
                    label="Target language",
                    custom_id="target_language",
                    style=TextInputStyle.short,
                    required=True,
                    max_length=50,
                    placeholder="e.g., Spanish, French, German..."
                )
            ]
        )
        await inter.response.send_modal(modal)

    async def _send_embed(self, inter: ApplicationCommandInteraction, title: str, description: str, color: Color, ephemeral: bool = True) -> None:
        embed = Embed(title=title, description=description, color=color)
        await inter.response.send_message(embed=embed, ephemeral=ephemeral)

def setup(bot):
    bot.add_cog(TranslationCog(bot))