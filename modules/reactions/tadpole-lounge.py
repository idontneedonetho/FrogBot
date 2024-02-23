# modules.reactions.tadpole-lounge

from datetime import datetime, timedelta, timezone
import disnake

async def add_role(member, role, channel):
    try:
        await member.add_roles(role)
        await channel.send(f"Hello {member.mention}, welcome to {member.guild.name}! You have been assigned the {role.mention} role. Please read the rules and enjoy your stay! You will gain full server access in a little while.")
    except Exception as e:
        print(f"Error adding role {role.name} to member {member.name}: {e}")

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
