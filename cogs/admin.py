import discord
from discord.ext import commands

import sympy

from cogs.utils.search import search

class AdminCog:
	"""Admin commands"""

	def __init__(self, bot):
		self.bot = bot
		self.embedcolor = 0x78A064

	async def __local_check(self, ctx):
		if await self.bot.is_owner(ctx.author):
			return True
		else:
			await ctx.send('Command is only avaliable for bot owner.')
			return False

	@commands.command()
	async def eval(self, ctx, *, input):
		return str(sympy.sympify(input))

	@commands.command(aliases=['f'], hidden=True)
	async def forum(self, ctx, *, query):
		await ctx.invoke(self.search, query='site:autohotkey.com ' + query)

	@commands.command(aliases=['g'], hidden=True)
	async def search(self, ctx, *, query):
		result = search(query)
		if not result:
			await ctx.send('No results.')
		else:
			embed = discord.Embed(title=result['title'], url=result['url'], description=result['description'], color=self.embedcolor)
			embed.set_footer(text=result['domain'])
			await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(AdminCog(bot))