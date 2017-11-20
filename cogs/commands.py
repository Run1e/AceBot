import discord
from discord.ext import commands

import traceback
import requests
import random
import time
import math
import json
import datetime
import asyncio

import wikipedia

class Commands:
	"""Contains global commands"""

	def __init__(self, bot):
		self.bot = bot

		#self.bot.remove_command('help')

		self.time = time.time()
		self.reptime = {}

		# simple reply
		self.replies = {
			'\o': 'o/',
			'o/': '\o'
		}

		with open('cogs/data/facts.txt', 'r') as f:
			self.splitfacts = f.read().splitlines()
		with open('lib/wolfram.txt', 'r') as f:
			self.wolframkey = f.read()
		with open('lib/weather.txt', 'r') as f:
			self.weather_key = f.read()
		with open('lib/oxford.txt', 'r') as f:
			self.oxford = f.read().splitlines()
		with open('lib/rep.json', 'r') as f:
			self.reps = json.loads(f.read())

	async def on_command_error(self, ctx, error):
		if isinstance(error, (commands.CommandNotFound,)):
			return

		if isinstance(error, commands.CheckFailure) and ctx.command.cog_name == 'Admin':
			return await ctx.send('Commands only avaliable for bot owner.')
		if isinstance(error, commands.DisabledCommand):
			return await ctx.send('Command has been disabled.')
		if isinstance(error, commands.MissingPermissions):
			return await ctx.send('Invoker is missing permissions to run this command.')
		if isinstance(error, commands.BotMissingPermissions):
			return await ctx.send('Bot is missing permissions to run this command.')

		# standard error message
		if isinstance(error, (discord.Forbidden,)):
			return await ctx.send(f'An error occured in `{ctx.command.name}` invoked by {ctx.message.author}:\n```{error}```')

		# argument error
		if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument, commands.TooManyArguments)):
			self.bot.formatter.context = ctx
			self.bot.formatter.command = ctx.command
			return await ctx.send(f'Arguments provided are malformed.\n```{self.bot.formatter.get_command_signature()}```')

		print(f'\n\n{error}\n')
		#traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)

	async def on_message(self, message):
		if message.author.bot:
			return

		if message.content in self.replies:
			ctx = await self.bot.get_context(message)
			await ctx.send(self.replies[message.content])

	async def embedwiki(self, ctx, wiki):
		embed = discord.Embed()

		sum = wiki.summary
		if len(sum) > 1024:
			sum = sum[0:1024] + '...'

		embed.description = sum
		embed.set_author(name=wiki.title, url=wiki.url, icon_url='https://i.imgur.com/qIor1ag.png')

		image = ''
		for img in wiki.images:
			if not img.endswith('.svg'):
				image = img
				break

		if image:
			embed.set_image(url=image)

		embed.set_footer(text='wikipedia.com')
		await ctx.send(embed=embed)

	@commands.command()
	async def weather(self, ctx, *, location: str = None):
		"""Check the weather in a location."""
		if location is None:
			return await ctx.send('Please provide a location to get Weather Information for.')

		base = f'http://api.apixu.com/v1/current.json?key={self.weather_key}&q={location}'

		try:
			res = requests.get(base)
			data = json.loads(res.text)
		except:
			return await ctx.send('Failed getting weather information.')

		location = data['location']
		locmsg = f'{location["name"]}, {location["region"]} {location["country"].upper()}'
		current = data['current']

		embed = discord.Embed(title=f'Weather for {locmsg}', description=f'*{current["condition"]["text"]}*')
		embed.set_thumbnail(url=f'http:{current["condition"]["icon"]}')
		embed.add_field(name='Temperature', value=f'{current["temp_c"]}°C | {current["temp_f"]}°F')
		embed.add_field(name='Feels Like', value=f'{current["feelslike_c"]}°C | {current["feelslike_f"]}°F')
		embed.add_field(name='Precipitation', value=f'{current["precip_mm"]} mm')
		embed.add_field(name='Humidity', value=f'{current["humidity"]}%')
		embed.add_field(name='Windspeed', value=f'{current["wind_kph"]} kph | {current["wind_mph"]} mph')
		embed.add_field(name='Wind Direction', value=current['wind_dir'])
		embed.timestamp = datetime.datetime.utcnow()

		await ctx.send(content=None, embed=embed)

	@commands.command(name='8')
	async def ball(self, ctx, question):
		"""Classic Magic 8 Ball"""
		responses = (
			'It is certain', # yes
			'It is decidedly so',
			'Without a doubt',
			'Yes definitely',
			'You may rely on it',
			'As I see it, yes',
			'Most likely',
			'Outlook good',
			'Yes',
			'Signs point to yes', # uncertain
			'Reply hazy try again',
			'Ask again later',
			'Better not tell you now',
			'Cannot predict now',
			'Concentrate and ask again',
			"Don't count on it", # no
			'My reply is no',
			'My sources say no',
			'Outlook not so good',
			'Very doubtful'
		)
		await ctx.trigger_typing()
		await asyncio.sleep(3)
		await ctx.send(random.choice(responses))

	@commands.command(hidden=True)
	async def vote(self, ctx, question: str, time: int, *choices):
		return
		if len(choices) > 9:
			return await ctx.send('Too many choices!')

		await ctx.message.delete()

		if time > 60:
			time = 60
		elif time < 5:
			time = 5

		msg_content = f'{ctx.message.author.mention} has just started a vote!\n\n***{question}***\n\n'

		for i, choice in enumerate(choices):
			msg_content += f'**{i + 1}** - {choice}\n'

		msg_content += f'\nVote ends in {time} seconds. Vote with reactions below!'

		msg = await ctx.send(msg_content)

		for i, choice in enumerate(choices):
			await msg.add_reaction(f'{i + 1}\u20e3')

		await asyncio.sleep(time)

		print('fin')
		print(msg.reactions)

	@commands.command()
	async def choose(self, ctx, *choices):
		"""Choose from a list."""
		await ctx.send(random.choice(choices))

	@commands.command(aliases=['wiki'])
	async def wikipedia(self, ctx, *, query):
		"""Preview a Wikipedia article."""

		await ctx.trigger_typing()
		try:
			wiki = wikipedia.page(query)
		except:
			return await ctx.send('No results.')

		await self.embedwiki(ctx, wiki)

	@commands.command()
	async def wikirandom(self, ctx):
		"""Get a random wikipedia page."""

		await ctx.trigger_typing()
		try:
			page_name = wikipedia.random(1)
		except:
			return await ctx.invoke(self.wikirandom)

		try:
			wiki = wikipedia.page(page_name)
			for attr in ('summary', 'url', 'title'):
				if not hasattr(wiki, attr):
					return await ctx.invoke(self.wikirandom)
		except wikipedia.exceptions.DisambiguationError as e:
			return await ctx.invoke(self.wikirandom)
		await self.embedwiki(ctx, wiki)

	@commands.command(aliases=['def'])
	async def define(self, ctx, *, query):
		"""Define a word using Oxfords dictionary."""

		await ctx.trigger_typing()

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

		await ctx.trigger_typing()

		req = requests.get('https://api.wolframalpha.com/v1/result?i={}&appid={}'.format(query, self.wolframkey))
		text = f'Query:\n```python\n{query}``` \nResult:\n```python\n{req.text}``` '
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
	async def info(self, ctx):
		await ctx.send(f'```{self.bot.description}\n\nFramework: discord.py {discord.__version__}\nSource: https://github.com/Run1e/AceBot```')

	@commands.command(hidden=True)
	async def uptime(self, ctx):
		sec = time.time() - self.time
		seconds = math.floor(sec % 60)
		minutes = math.floor(sec/60 % 60)
		hours = math.floor(sec/60/60 % 24)
		days = math.floor(sec/60/60/24)
		await ctx.send('{}d {:02d}:{:02d}:{:02d}'.format(days, hours, minutes, seconds))

	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.author.mention}!')

	@commands.command(hidden=True)
	async def shrug(self, ctx):
		await ctx.send('¯\_(ツ)_/¯')

	@commands.command(hidden=True)
	async def source(self, ctx):
		await ctx.send('https://github.com/Run1e/AceBot')

	@commands.command(hidden=True)
	async def demo(self, ctx):
		await ctx.send('https://i.imgur.com/Iu04Jro.gifv')

	@commands.command()
	async def rep(self, ctx):
		"""Give someone some reputation!"""

		# see if anyone was mentioned, if not just return how many points the author has
		try:
			mention = ctx.message.mentions[0]
		except:
			return await ctx.send(f'{ctx.author.mention} has a reputation of {(self.reps[str(ctx.author.id)] if str(ctx.author.id) in self.reps else 0)}!')

		# get the id
		id = str(mention.id)

		# make sure people can't rep themselves
		if id == ctx.author.id:
			return await ctx.send(":japanese_goblin:")

		# make sure a reptime object exists for the author
		if not ctx.author.id in self.reptime:
			self.reptime[ctx.author.id] = {}

		# make sure the repee has an entry, and if it already does, make sure it's outside of the reptime
		if not id in self.reptime[ctx.author.id]:
			self.reptime[ctx.author.id][id] = time.time()
		else:
			if time.time() - self.reptime[ctx.author.id][id] < 90:
				return await ctx.send("Woah! You shouldn't be repping *that* fast.")
			else:
				self.reptime[ctx.author.id][id] = time.time()

		# make sure the repee has a key
		if not id in self.reps:
			self.reps[id] = 0

		# increment
		self.reps[id] += 1

		# save the new json
		open('cogs/data/rep.json', 'w').write(json.dumps(self.reps))

		if id == str(self.bot.user.id):
			await ctx.send(f'Thanks {ctx.author.mention}! I now have {self.reps[id]} rep points! :blush: ')
		else:
			await ctx.send(f'{mention.mention} now has {self.reps[id]} rep points!')

def setup(bot):
	bot.add_cog(Commands(bot))