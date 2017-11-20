import discord
from discord.ext import commands

class ClassOne:
	def __init__(self, bot):
		self.bot = bot
		self.guilds = (372163679010947074,)

	async def __local_check(self, ctx):
		return ctx.guild.id in self.guilds

	@commands.command(name='beta+')
	async def betaplus(self, ctx):
		"""Add yourself to the Beta Access role."""
		role = discord.utils.get(ctx.guild.roles, name="Beta Access")
		await ctx.author.add_roles(role)
		await ctx.send('Added to Beta Access!')

	@commands.command(name='beta-')
	async def betaminus(self, ctx):
		"""Remove yourself from the Beta Access role."""
		role = discord.utils.get(ctx.guild.roles, name="Beta Access")
		await ctx.author.remove_roles(role)
		await ctx.send('Removed from Beta Access.')

def setup(bot):
	bot.add_cog(ClassOne(bot))