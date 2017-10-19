import discord
from discord.ext import commands

import requests
import random

with open('cogs/commands/facts.txt', 'r') as f:
	splitfacts = f.read().splitlines()

with open('lib/wolfram.txt', 'r') as f:
	wolfram = f.read()

class CommandCog:
	def __init__(self, bot):
		self.bot = bot
		self.embedcolor = 0x78A064

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

	@commands.command()
	async def flip(self, ctx):
		"""Flip a coin!"""
		await ctx.send(random.choice(['Heads', 'Tails']) + '!')

	@commands.command(aliases=['num'])
	async def number(self, ctx, *, num: int):
		"""Get a random fact about a number!"""
		req = requests.get('http://numbersapi.com/{}?notfound=floor'.format(num))
		await ctx.send(req.text)

	@commands.command()
	async def fact(self, ctx):
		"""Get a fun fact!"""
		await ctx.send(random.choice(splitfacts))

def setup(bot):
	bot.add_cog(CommandCog(bot))