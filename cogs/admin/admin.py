import discord
from discord.ext import commands

from cogs.search import search

class AdminCog:
	def __init__(self, bot):
		self.bot = bot
		self.embedcolor = 0x78A064

	async def __local_check(self, ctx):
		if await self.bot.is_owner(ctx.author):
			return True
		else:
			await ctx.send('Command is only avaliable for bot owner.')
			return False

	@commands.command(aliases=['f'], hidden=True)
	async def forum(self, ctx, *, input):
		await ctx.invoke(self.search, input='site:autohotkey.com ' + input)

	@commands.command(aliases=['g'], hidden=True)
	async def search(self, ctx, *, input):
		result = search(input)
		if not result:
			await ctx.send('No results.')
		else:
			await ctx.send(embed=discord.Embed(**result, color=0x78A064))

def setup(bot):
	bot.add_cog(AdminCog(bot))