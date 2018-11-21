import discord, logging
from discord.ext import commands

from utils.setup_logger import config_logger
log = logging.getLogger(__name__)
log = config_logger(log)

ROLES_CHANNEL 	= 513071256283906068
ROLES 			= {
	345652145267277836: '💻', # helper
	513078270581932033: '🕹', # lounge
	513111956425670667: '🇭', # hotkey crew
	513111654112690178: '🇬', # gui crew
	513111541663662101: '🇴', # oop crew
	513111591361970204: '🇷'  # regex crew
}

class Roles:
	def __init__(self, bot):
		self.bot = bot
		
	async def on_raw_reaction_add(self, payload):
		if payload.channel_id != ROLES_CHANNEL:
			return
		
		channel = self.bot.get_channel(payload.channel_id)
		msg = await channel.get_message(payload.message_id)
		if msg.author.id != self.bot.user.id:
			return
		
		guild = self.bot.get_guild(payload.guild_id)
		member = guild.get_member(payload.user_id)
		if member.bot:
			return
		
		await msg.remove_reaction(payload.emoji, member)
		
		action = None
		
		for role_id, emoji in ROLES.items():
			if emoji == str(payload.emoji):
				role = guild.get_role(role_id)
				action = True
				desc = f'{member.mention} -> {role.mention}'
				if role in member.roles:
					await member.remove_roles(role)
					title = 'Removed Role'
				else:
					await member.add_roles(role)
					title = 'Added Role'
		
		if action:
			log.info(f'{title} {role.name} to {member.name}')
			await channel.send(embed=discord.Embed(title=title, description=desc), delete_after=5)
		
	@commands.command(hidden=True)
	@commands.is_owner()
	async def roles(self, ctx):
		if ctx.channel.id != ROLES_CHANNEL:
			return
		
		await ctx.message.delete()
		await ctx.channel.purge()
		
		roles = []
		for role_id in ROLES:
			roles.append(ctx.guild.get_role(role_id))
			
		e = discord.Embed(description='Click the reactions to add yourselves to a role!')
		
		for role in roles:
			e.add_field(name=ROLES[role.id], value=role.mention)
			
		msg = await ctx.send(embed=e)
		
		for role in roles:
			await msg.add_reaction(ROLES[role.id])

def setup(bot):
	bot.add_cog(Roles(bot))