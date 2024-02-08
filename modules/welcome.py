import asyncio
import random
import json

async def on_member_join(member):
    welcome_channel = member.guild.system_channel
    if not welcome_channel:
        return
    try:
        with open("non_successful_spawns.json", "r") as f:
            data = json.load(f)
            non_successful_spawns = data.get(str(member.guild.id), 0)
    except FileNotFoundError:
        non_successful_spawns = 0
    gif_links = ["https://cdn3.emoji.gg/emojis/1463-wave.gif"] * 49 + \
                ["https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif"] * 49 + \
                ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"]  # The 1% GIF
    await asyncio.sleep(5)
    selected_gif = random.choice(gif_links)
    success_chance = 0.05 + non_successful_spawns * 0.05
    if random.random() < success_chance or non_successful_spawns >= 20:
        if selected_gif == "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif":
            message = f"GLUB GLUB GLUB {member.mention}!!!"
        else:
            message = f"Hello {member.mention}!"
        try:
            await welcome_channel.send(message)
            await welcome_channel.send(selected_gif)
            non_successful_spawns = 0
        except Exception as e:
            print(f"Failed to send welcome message or gif: {e}")
    else:
        non_successful_spawns += 1
    with open("non_successful_spawns.json", "w") as f:
        data = {str(member.guild.id): non_successful_spawns}
        json.dump(data, f)

def setup(client):
    client.add_listener(on_member_join)