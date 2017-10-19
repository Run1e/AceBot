import discord
from discord.ext import commands

import requests
import random
import time
import math
import json

with open('cogs/data/facts.txt', 'r') as f:
	splitfacts = f.read().splitlines()

with open('lib/wolfram.txt', 'r') as f:
	wolfram = f.read()

with open('lib/oxford.txt', 'r') as f:
	oxford = f.read().splitlines()

class CommandCog:
	"""Contains global commands"""

	def __init__(self, bot):
		self.bot = bot
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

	@commands.command(aliases=['def'])
	async def define(self, ctx, *, query):
		"""Define a word using Oxfords dictionary."""
		req = requests.get('https://od-api.oxforddictionaries.com:443/api/v1/entries/en/' + query.split('\n')[0].lower(), headers={'Accept': 'application/json', 'app_id': oxford[0], 'app_key': oxford[1]})
		try:
			info = json.loads(req.text)
		except:
			return await ctx.send("Couldn't process query.")
		result = info['results'][0]
		entry = result['lexicalEntries'][0]

		word = result['word']
		type = entry['lexicalCategory']
		desc = entry['entries'][0]['senses'][0]['definitions'][0]

		word = word[:1].upper() + word[1:]
		desc = desc[:1].upper() + desc[1:]

		embed = discord.Embed(title=f'{word} ({type})', description=f'```{desc}```')
		embed.set_footer(text='Oxford University Press', icon_url='https://i.imgur.com/7GMY4dP.png')

		await ctx.send(embed=embed)

	@commands.command(aliases=['w'])
	async def wolfram(self, ctx, *, query):
		"""Queries wolfram."""
		req = requests.get('https://api.wolframalpha.com/v1/result?i={}&appid={}'.format(query, wolfram))
		text = f'Query:\n```{query}``` \nResult\n```{req.text}``` '
		embed = discord.Embed(description=text)
		embed.set_author(name='Wolfram Alpha', icon_url='https://i.imgur.com/KFppH69.png')
		embed.set_footer(text='wolframalpha')
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