# modules.reactions.tadpole-lounge

from datetime import datetime, timedelta, timezone
import disnake

async def add_role(member, role, channel):
    try:
        await member.add_roles(role)
    except Exception as e:
        print(f"Error adding role {role.name} to member {member.name}: {e}")
    try:
        await channel.send(f"Hello blank, welcome to blank! You have been assigned the blank role. Please read the rules and enjoy your stay! You will gain full server access in a little while. If you have any questions feel free to ask them here.")
    except Exception as e:
        print(f"Error sending to channel")
    try:
        await channel.send(f"Hello {member.mention}, welcome to blank! You have been assigned the blank role. Please read the rules and enjoy your stay! You will gain full server access in a little while. If you have any questions feel free to ask them here.")
    except Exception as e:
        print(f"Error with member mention: {member.mention}")
    try:
        await channel.send(f"Hello blank, welcome to {member.guild.name}! You have been assigned the blank role. Please read the rules and enjoy your stay! You will gain full server access in a little while. If you have any questions feel free to ask them here.")
    except Exception as e:
        print(f"Error with member.guild.name: {member.guild.name}")
    try:
        await channel.send(f"Hello blank, welcome to blank! You have been assigned the {role.mention} role. Please read the rules and enjoy your stay! You will gain full server access in a little while. If you have any questions feel free to ask them here.")
    except Exception as e:
        print(f"Error with role mention: {role.mention}")
        
        

async def on_member_join(member):
    try:
        role = disnake.utils.get(member.guild.roles, name="tadpole")
        channel = member.guild.get_channel(1208256502645657611)
        utcnow_aware = datetime.utcnow().replace(tzinfo=timezone.utc)
        if utcnow_aware - member.created_at < timedelta(days=2):
            await add_role(member, role, channel)
    except Exception as e:
        print(f"Error in on_member_join: {e}")

def setup(bot):
    bot.add_listener(on_member_join, "on_member_join")
