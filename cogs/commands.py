import discord
from discord.ext import commands

import requests
import random
import time
import math
import json

class CommandCog:
	"""Contains global commands"""

	def __init__(self, bot):
		self.bot = bot
		self.time = time.time()
		self.reptime = {}

		# simple reply
		self.replies = {
			'\o': 'o/',
			'o/': '\o'
		}

		# list of commands to ignore
		self.ignore_cmds = (
			'clear', 'mute', 'levels', 'rank', 'mute',
			'unmute', 'manga', 'pokemon', 'urban', 'imgur',
			'anime', 'twitch', 'youtube'
		)

		with open('cogs/data/facts.txt', 'r') as f:
			self.splitfacts = f.read().splitlines()
		with open('lib/wolfram.txt', 'r') as f:
			self.wolframkey = f.read()
		with open('lib/oxford.txt', 'r') as f:
			self.oxford = f.read().splitlines()
		with open('cogs/data/rep.json', 'r') as f:
			self.reps = json.loads(f.read())

	async def __local_check(self, ctx):
		if ctx.message.author.id == self.bot.user.id:
			return False
		if ctx.message.author.id in self.bot.ignore_users:
			return False

		return True

	async def on_message(self, message):
		# stop if we're running a "command"
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# get the message context
		ctx = await self.bot.get_context(message)

		if not await self.__local_check(ctx):
			return

		# see if the message has a reply
		if message.content in self.replies:
			return await ctx.send(self.replies[message.content])

	@commands.command()
	async def rep(self, ctx):
		"""Give someone some reputation!"""

		# see if anyone was mentioned, if not just return how many points the author has
		try:
			mention = ctx.message.mentions[0]
		except:
			return await ctx.send(f'{ctx.message.author.mention} has a reputation of {(self.reps[str(ctx.message.author.id)] if str(ctx.message.author.id) in self.reps else 0)}!')

		# get the id
		id = mention.id

		# make sure people can't rep themselves
		if id == ctx.message.author.id:
			return await ctx.send(":japanese_goblin:")

		# make sure a reptime object exists for the author
		if not ctx.message.author.id in self.reptime:
			self.reptime[ctx.message.author.id] = {}

		# make sure the repee has an entry, and if it already does, make sure it's outside of the reptime
		if not id in self.reptime[ctx.message.author.id]:
			self.reptime[ctx.message.author.id][id] = time.time()
		else:
			if time.time() - self.reptime[ctx.message.author.id][id] < 60:
				return await ctx.send("Woah! You shouldn't be repping *that* fast.")
			else:
				self.reptime[ctx.message.author.id][id] = time.time()

		# make sure the repee has a key
		if not str(id) in self.reps:
			self.reps[str(id)] = 0

		# increment
		self.reps[str(id)] += 1

		# save the new json
		open('cogs/data/rep.json', 'w').write(json.dumps(self.reps))

		await ctx.send(f'{mention.mention} now has {self.reps[str(id)]} rep points!')

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
		req = requests.get('https://od-api.oxforddictionaries.com:443/api/v1/entries/en/' + query.split('\n')[0].lower(), headers={'Accept': 'application/json', 'app_id': self.oxford[0], 'app_key': self.oxford[1]})
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

	@commands.command()
	async def flip(self, ctx):
		"""Flip a coin!"""
		await ctx.send(random.choice(['Heads', 'Tails']) + '!')

	@commands.command(aliases=['w'])
	async def wolfram(self, ctx, *, query):
		"""Queries wolfram."""
		req = requests.get('https://api.wolframalpha.com/v1/result?i={}&appid={}'.format(query, self.wolframkey))
		text = f'Query:\n```python\n{query}``` \nResult\n```python\n{req.text}``` '
		embed = discord.Embed(description=text)
		embed.set_author(name='Wolfram Alpha', icon_url='https://i.imgur.com/KFppH69.png')
		embed.set_footer(text='wolframalpha.com')
		if len(text) > 2000:
			await ctx.send('Response too large.')
		else:
			await ctx.send(embed=embed)

	@commands.command(aliases=['num'])
	async def number(self, ctx, *, num: int):
		"""Get a random fact about a number!"""
		req = requests.get('http://numbersapi.com/{}?notfound=floor'.format(num))
		await ctx.send(req.text)

	@commands.command()
	async def fact(self, ctx):
		"""Get a fun fact!"""
		await ctx.send(random.choice(self.splitfacts))

	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.message.author.mention}!')

	@commands.command(hidden=True)
	async def shrug(self, ctx):
		await ctx.send('¯\_(ツ)_/¯')

	@commands.command(hidden=True)
	async def source(self, ctx):
		await ctx.send('https://github.com/Run1e/A_AhkBot')

def setup(bot):
	bot.add_cog(CommandCog(bot))