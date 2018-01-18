import discord
from discord.ext import commands

class Roles:
	def __init__(self, bot):
		self.bot = bot

		self.guilds = {
			115993023636176902: {
				'helper': 'Helpers'
			},
			395956681793863690: {
				'helper': 'helpers'
			}
		}

		seen = []
		for guild, roles in self.guilds.items():
			for command, role in roles.items():
				self.guilds[guild][command] = self.get_role(guild, role)
				if command in seen:
					continue
				seen.append(command)
				self.bot.add_command(commands.Command(name=command + "+", callback=self.add_role))
				self.bot.add_command(commands.Command(name=command + "-", callback=self.remove_role))


	def get_role(self, guild_id, role_name):
		guild = self.bot.get_guild(guild_id)
		return discord.utils.get(guild.roles, name=role_name)

	async def add_role(self, ctx):
		role = self.guilds[ctx.guild.id][ctx.invoked_with[:-1]]
		try:
			await ctx.author.add_roles(role)
		except:
			await ctx.send(f"Failed adding you to the role.")
		await ctx.send(f"Added to {role.name}!")

	async def remove_role(self, ctx):
		role = self.guilds[ctx.guild.id][ctx.invoked_with[:-1]]
		try:
			await ctx.author.remove_roles(role)
		except:
			await ctx.send(f"Failed removing you from role.")
		await ctx.send(f"Removed from {role.name}.")

def setup(bot):
	bot.add_cog(Roles(bot))