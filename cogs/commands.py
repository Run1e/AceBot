import discord
from discord.ext import commands

import requests
import random
import time
import math

with open('cogs/data/facts.txt', 'r') as f:
	splitfacts = f.read().splitlines()

with open('lib/wolfram.txt', 'r') as f:
	wolfram = f.read()

class CommandCog:
	"""Contains global commands"""

	def __init__(self, bot):
		self.bot = bot
		self.embedcolor = 0x78A064
		self.time = time.time()

	@commands.command()
	async def uptime(self, ctx):
		"""Return the uptime of the bot."""
		sec = time.time() - self.time
		seconds = math.floor(sec % 60)
		minutes = math.floor(sec/60 % 60)
		hours = math.floor(sec/60/60 % 24)
		days = math.floor(sec/60/60/24)
		await ctx.send('{}d {:02d}:{:02d}:{:02d}'.format(days, hours, minutes, seconds))


	@commands.command(aliases=['w'])
	async def wolfram(self, ctx, *, query):
		"""Queries wolfram."""
		key = wolfram
		req = requests.get('https://api.wolframalpha.com/v1/result?i={}&appid={}'.format(query, key))
		text = '**Query:**\n{}\n\n**Result:**\n{}'.format(query.replace('*', '\*'), req.text.replace('*', '\*'))
		embed = discord.Embed(description=text, color=0x78A064)
		embed.set_author(name='Wolfram Alpha', icon_url='https://i.imgur.com/KFppH69.png')
		embed.set_footer(text='wolframalpha.com')
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