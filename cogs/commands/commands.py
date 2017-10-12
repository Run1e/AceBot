import discord
from discord.ext import commands

from cogs.search import search

import requests
import random

with open("cogs/commands/facts.txt", "r") as f:
	facts = f.read()

class CommandCog:
	def __init__(self, bot):
		self.bot = bot

	@commands.command(aliases=['g'], hidden=True)
	async def search(self, ctx, *, input):
		if ctx.author.id != 265644569784221696:
			return
		result = search(input)
		if result:
			await ctx.send(embed=discord.Embed(**result, color=0x78A064))

	@commands.command(aliases=['num'])
	async def number(self, ctx, *, num: int):
		"""Get a random fact about a number!"""
		req = requests.get('http://numbersapi.com/{}?notfound=floor'.format(num))
		await ctx.send(req.text)

	@commands.command()
	async def fact(self, ctx):
		"""Get a fun fact!"""
		await ctx.send(random.choice(facts.splitlines()))

def setup(bot):
	bot.add_cog(CommandCog(bot))