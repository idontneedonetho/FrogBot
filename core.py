# core.py

import discord
import os
import traceback
from datetime import datetime, timedelta
from discord.ext import commands
from dotenv import load_dotenv
from module_loader import ModuleLoader
from modules.roles import check_user_points
from modules.utils.commons import frog_version, fetch_reply_chain, send_long_message
from modules.utils.GPT import ask_gpt
from modules.utils.search import estimate_confidence, determine_information_type, handle_query

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
user_request_times = {}
RATE_LIMIT = timedelta(seconds=5)

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.messages = True
intents.message_content = True
intents.guild_messages = True
intents.reactions = True
client = commands.Bot(command_prefix=commands.when_mentioned, intents=intents, case_insensitive=True)
module_loader = ModuleLoader('modules')
module_loader.load_modules(client)

@client.event
async def on_ready():
    await check_user_points(client)
    await client.change_presence(activity=discord.Game(name=f"@FrogBot help | {frog_version}"))
    print(f'Logged in as {client.user.name}')
    try:
        with open("restart_channel_id.txt", "r") as file:
            channel_id = int(file.read().strip())
            channel = client.get_channel(channel_id)
            if channel:
                await channel.send("I'm back online!")
            os.remove("restart_channel_id.txt")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error sending restart message: {e}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    for handler in module_loader.get_event_handlers('on_message'):
        await handler(message)
    if client.user.mentioned_in(message):
        content = message.content.replace(client.user.mention, '').strip()
        if content:
            ctx = await client.get_context(message)
            if ctx.valid:
                await client.process_commands(message)
            else:
                current_time = datetime.now()
                last_request_time = user_request_times.get(message.author.id)
                if last_request_time and current_time - last_request_time < RATE_LIMIT:
                    try:
                        await message.reply("You are sending messages too quickly. Please wait a moment before trying again.")
                    except discord.HTTPException:
                        await message.channel.send("Could not send the rate limit message; the original message might have been deleted.")
                    return
                user_request_times[message.author.id] = current_time
                async with message.channel.typing():
                    info_type = determine_information_type(content)
                    if info_type == "Fresh Information":
                        search_response = await handle_query(content)
                        response = search_response if search_response else "No relevant results found for the query."
                    else:
                        context = await fetch_reply_chain(message)
                        combined_messages = [{'content': msg, 'role': 'user'} for msg in context]
                        combined_messages.append({'content': content, 'role': 'user'})
                        response = await ask_gpt(combined_messages)
                        if not estimate_confidence(response):
                            print("Fetching additional information for uncertain queries.")
                            search_response = await handle_query(content)
                            response = search_response if search_response else "I'm sorry, I couldn't find information on that topic."
                    response = response.replace(client.user.name + ":", "").strip()
                    await send_long_message(message, response)
    else:
        await client.process_commands(message)

@client.event
async def on_reaction_add(reaction, user):
    for handler in module_loader.get_event_handlers('on_reaction_add'):
        await handler(reaction, user)

@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, I didn't understand that command.")
    else:
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        tb_str = "".join(tb)
        print(f'An error occurred: {error}\n{tb_str}')

client.run(TOKEN)
