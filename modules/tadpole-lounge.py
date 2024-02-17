from datetime import datetime, timedelta
import discord

channel = discord.utils.get(member.guild.channels, name="tadpole-lounge")

@bot.event
async def on_member_join(member):
    role = discord.utils.get(member.guild.roles, name="tadpole")
    if datetime.utcnow() - member.created_at < timedelta(days=2):
        await member.add_roles(role)
        await channel.send(f"Hello {member.mention}, welcome to {member.guild.name}! You have been assigned the {role.mention} role. Please read the rules and enjoy your stay! You will gain full server access in a little while.")

@bot.command(pass_context=True)
async def setup(ctx):
    ctx.bot.add_listener(on_member_join, "on_member_join")