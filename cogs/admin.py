import discord
from discord.ext import commands

import sympy
import json

from cogs.utils.search import search

class AdminCog:
	"""Admin commands"""

	def __init__(self, bot):
		self.bot = bot

	async def __local_check(self, ctx):
		return await self.bot.is_owner(ctx.author)

	async def on_command_error(self, ctx, error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send('Command is only avaliable for bot owner.')

	@commands.command()
	async def say(self, ctx, *, text):
		await ctx.message.delete()
		await ctx.send(text)

	@commands.command()
	async def nick(self, ctx, *, nick):
		"""Change the bot nickname."""
		if len(nick):
			await self.bot.user.edit(username=nick)

	@commands.command()
	async def notice(self, ctx):
		"""Remove user for ignore list."""
		try:
			user = ctx.message.mentions[0].id
		except:
			return await ctx.send('No user specified.')

		if user not in self.bot.info['ignore_users']:
			return await ctx.send('User was never ignored.')

		self.bot.info['ignore_users'].remove(user)

		with open('cogs/data/ignore.json', 'w') as f:
			f.write(json.dumps(self.bot.info['ignore_users'], sort_keys=True, indent=4, separators=(',', ': ')))

		await ctx.send('User removed from ignore list.')

	@commands.command()
	async def ignore(self, ctx):
		"""Add user to ignore list."""
		try:
			user = ctx.message.mentions[0].id
		except:
			return await ctx.send('No user specified.')

		if user in self.bot.info['ignore_users']:
			return await ctx.send('User already ignored.')

		self.bot.info['ignore_users'].append(user)

		with open('cogs/data/ignore.json', 'w') as f:
			f.write(json.dumps(self.bot.info['ignore_users'], sort_keys=True, indent=4, separators=(',', ': ')))

		await ctx.send('User ignored.')

	@commands.command()
	async def eval(self, ctx, *, input):
		"""Evaluate a string using sympy."""
		await ctx.send(f'```python\n{str(sympy.sympify(input))}\n```')

	@commands.command(aliases=['gh'])
	async def github(self, ctx, *, query):
		"""Search for a GitHub repo."""
		await ctx.invoke(self.search, query='site:github.com ' + query)

	@commands.command(aliases=['f'])
	async def forum(self, ctx, *, query):
		"""Search for an AutoHotkey thread."""
		await ctx.invoke(self.search, query='site:autohotkey.com ' + query)

	@commands.command(aliases=['g'])
	async def search(self, ctx, *, query):
		"""Search Google."""
		result = search(query)
		if not result:
			await ctx.send('No results.')
		else:
			embed = discord.Embed(title=result['title'], url=result['url'], description=result['description'])
			embed.set_footer(text=result['domain'])
			await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(AdminCog(bot))