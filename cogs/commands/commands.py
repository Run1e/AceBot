import discord
from discord.ext import commands

from cogs.search import search

import requests
import random

with open('cogs/commands/facts.txt', 'r') as f:
	facts = f.read()

with open('lib/wolfram.txt', 'r') as f:
	wolfram = f.read()

class CommandCog:
	def __init__(self, bot):
		self.bot = bot
		self.trusted = (
			265644569784221696
		)

	@commands.command(aliases=['w'])
	async def wolfram(self, ctx, *, query):
		"""Queries wolfram."""
		key = wolfram
		req = requests.get('https://api.wolframalpha.com/v1/result?i={}&appid={}'.format(query, key))
		text = '**Query:**\n{}\n\n**Result:**\n{}'.format(query.replace('*', '\*'), req.text.replace('*', '\*'))
		embed = discord.Embed(title='Wolfram Alpha', description=text, color=0x78A064)
		if len(text) > 2000:
			await ctx.send('Response too large.')
		else:
			await ctx.send(embed=embed)

	@commands.command(aliases=['g'], hidden=True)
	async def search(self, ctx, *, input):
		if ctx.author.id not in self.trusted:
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