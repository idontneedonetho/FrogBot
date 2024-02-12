import asyncio
import random
import json

async def on_member_join(member):
    welcome_channel = member.guild.system_channel
    if welcome_channel:
        await asyncio.sleep(5)
        gif_links = ["https://cdn3.emoji.gg/emojis/1463-wave.gif"] * 49 + \
                    ["https://i.pinimg.com/originals/ab/bd/b6/abbdb6e66ec39dc9262abc617fbc2b02.gif"] * 49 + \
                    ["https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExYzhsN3Fnd2c1MG1hcmhwMG00czE5ZHZoZmZsa3k4N3hqcWJya2NwdiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5xtDarIELDLO7lSFQJi/giphy.gif"]
        non_successful_spawns = load_state()
        while non_successful_spawns < 20:
            selected_gif = random.choice(gif_links)
            if random.random() < 0.05 + non_successful_spawns * 0.05:
                try:
                    await asyncio.gather(
                        welcome_channel.send(f"Hello {member.mention}! If you need anything just ask!"),
                        welcome_channel.send(selected_gif)
                    )
                except Exception as e:
                    print(f"Failed to send welcome message or gif: {e}")
                    await asyncio.sleep(10)
                    continue
                break
            non_successful_spawns += 1
            save_state(non_successful_spawns)
        else:
            try:
                await asyncio.gather(
                    welcome_channel.send(f"Hello {member.mention}! If you need anything just ask!")
                )
            except Exception as e:
                print(f"Failed to send alternative welcome message: {e}")
                await asyncio.sleep(10)

def load_state():
    try:
        with open('state.json', 'r') as f:
            state = json.load(f)
            return state['non_successful_spawns']
    except FileNotFoundError:
        return 0

def save_state(non_successful_spawns):
    with open('state.json', 'w') as f:
        json.dump({'non_successful_spawns': non_successful_spawns}, f)

def setup(client):
    client.event(on_member_join)