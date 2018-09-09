import asyncio, math, random, time

from datetime import datetime

import aiohttp.client_exceptions as client_exceptions
import discord
from discord.ext import commands


class Commands:
	"""Contains global commands."""

	def __init__(self, bot):
		self.bot = bot

		# simple reply
		self.replies = {
			'\o': 'o/',
			'o/': '\o'
		}

		with open('data/facts.txt', 'r', encoding='utf-8-sig') as f:
			self.splitfacts = f.read().splitlines()

	async def on_message(self, message):
		if self.bot.blacklist(message):
			return

		if message.content in self.replies:
			await message.channel.send(self.replies[message.content])

	@commands.command()
	async def server(self, ctx):
		"""Show various information about the server."""

		statuses = {
			discord.Status.online: 0,
			discord.Status.idle: 0,
			discord.Status.dnd: 0,
			discord.Status.offline: 0
		}

		for member in ctx.guild.members:
			for status in statuses:
				if member.status is status:
					statuses[status] += 1

		att = {}
		att['Online'] = f'{sum(member.status is not discord.Status.offline for member in ctx.guild.members)}/{len(ctx.guild.members)}'
		att['Owner'] = ctx.guild.owner.display_name
		att['Channels'] = len(ctx.guild.text_channels) + len(ctx.guild.voice_channels)
		att['Region'] = str(ctx.guild.region)
		att['Created at'] = str(ctx.guild.created_at).split(' ')[0]

		e = discord.Embed(title=ctx.guild.name, description='\n'.join(f'**{a}**: {b}' for a, b in att.items()))
		e.set_thumbnail(url=ctx.guild.icon_url)
		e.set_footer(text=f'ID: {ctx.guild.id}')
		e.add_field(name='Status', value='\n'.join(str(status) for status in statuses))
		e.add_field(name='Users', value='\n'.join(str(count) for status, count in statuses.items()))
		await ctx.send(embed=e)

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command()
	async def weather(self, ctx, *, location: str = None):
		"""Check the weather at a location."""

		if location is None:
			return await ctx.send('Please provide a location to get weather information for.')

		await ctx.trigger_typing()

		url = 'http://api.apixu.com/v1/current.json'

		params = {
			'key': self.bot.config["apixu"],
			'q': location
		}

		data, content_type = await self.bot.request('get', url, params=params)

		if data is None:
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
		embed.timestamp = datetime.utcnow()

		await ctx.send(embed=embed)

	@commands.command(name='8')
	async def ball(self, ctx, question):
		"""Classic Magic 8 Ball"""
		responses = (
			'It is certain',  # yes
			'It is decidedly so',
			'Without a doubt',
			'Yes definitely',
			'You may rely on it',
			'As I see it, yes',
			'Most likely',
			'Outlook good',
			'Yes',
			'Signs point to yes',  # uncertain
			'Reply hazy try again',
			'Ask again later',
			'Better not tell you now',
			'Cannot predict now',
			'Concentrate and ask again',
			"Don't count on it",  # no
			'My reply is no',
			'My sources say no',
			'Outlook not so good',
			'Very doubtful'
		)
		await ctx.trigger_typing()
		await asyncio.sleep(3)
		await ctx.send(random.choice(responses))

	@commands.command()
	async def choose(self, ctx, *choices):
		"""Choose from a list."""
		await ctx.send(random.choice(choices))

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command(aliases=['def'])
	async def define(self, ctx, *, query):
		"""Define a word using Oxfords dictionary."""

		await ctx.trigger_typing()

		url = 'https://od-api.oxforddictionaries.com:443/api/v1/entries/en/' + query.split('\n')[0].lower()

		headers = {
			'Accept': 'application/json',
			'app_id': self.bot.config['oxford']['id'],
			'app_key': self.bot.config['oxford']['key']
		}

		info, content_type = await self.bot.request('get', url, headers=headers)

		if info is None:
			return await ctx.send('Failed getting definition.')

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
		msg = await ctx.send('Flipping...')
		await asyncio.sleep(3)
		await msg.edit(content=random.choice(["Heads!", "Tails!"]))

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command(aliases=['w'])
	async def wolfram(self, ctx, *, query):
		"""Queries wolfram."""

		await ctx.trigger_typing()

		url = 'https://api.wolframalpha.com/v1/result'

		params = {
			'appid': self.bot.config["wolfram"],
			'i': query
		}

		res, content_type = await self.bot.request('get', url, params=params)

		if res is None:
			return await ctx.send('Wolfram request failed.')

		text = f'Query:\n```python\n{query}```\nResult:\n```python\n{res}```'
		embed = discord.Embed(description=text)
		embed.set_author(name='Wolfram Alpha', icon_url='https://i.imgur.com/KFppH69.png')
		embed.set_footer(text='wolframalpha.com')
		if len(text) > 2000:
			await ctx.send('Response too long.')
		else:
			await ctx.send(embed=embed)

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command(hidden=True)
	async def breed(self, ctx):
		"""Shows info about a random dog breed!"""
		pass

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command()
	async def meow(self, ctx):
		"""Gets a random cat picture/gif!"""

		url = 'http://thecatapi.com/api/images/get'
		params = {
			'format': 'src',
			'api_key': self.bot.config['catapikey']
		}

		for attempt in range(3):
			await ctx.trigger_typing()

			data, content_type = await self.bot.request('get', url, params=params)
			if data is None:
				return
			file = discord.File(data, 'cat.' + content_type.split('/')[1])
			return await ctx.send(file=file)

		await ctx.send('thecatapi request failed.')

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command()
	async def woof(self, ctx):
		"""Gets a random dog picture/gif!"""

		url = 'https://random.dog/'
		params = {
			'filter': 'mp4'
		}

		for attempt in range(3):
			await ctx.trigger_typing()

			# get id of dig image
			id, content_type = await self.bot.request('get', url + 'woof', params=params)
			if id is None:
				continue

			# fetch actual dog image
			data, content_type = await self.bot.request('get', url + id)
			if data is None:
				continue

			# upload it
			file = discord.File(data, 'dog.' + content_type.split('/')[1])
			return await ctx.send(file=file)

		await ctx.send('random.dog request failed.')

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command()
	async def quack(self, ctx):
		"""Gets a random duck picture/gif!"""

		url = 'https://random-d.uk/api/v1/random'

		for attempt in range(3):
			await ctx.trigger_typing()

			json, content_type = await self.bot.request('get', url)
			if json is None:
				continue

			data, content_type = await self.bot.request('get', json['url'])
			if data is None:
				continue

			file = discord.File(data, 'duck.' + content_type.split('/')[1])
			return await ctx.send(file=file)

		await ctx.send('random-d.uk request failed.')

	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command(aliases=['num'])
	async def number(self, ctx, *, num: int):
		"""Get a random fact about a number!"""

		text, content_type = await self.bot.request('get', f'http://numbersapi.com/{num}?notfound=floor')

		if text is None:
			return await ctx.send('Number API request failed.')

		await ctx.send(text)

	@commands.command()
	async def fact(self, ctx):
		"""Get a fun fact!"""
		await ctx.send(random.choice(self.splitfacts))

	@commands.command(hidden=True)
	async def info(self, ctx):
		await ctx.send(
			f'```{self.bot.description}\n\nFramework: discord.py {discord.__version__}\nSource: https://github.com/Run1e/AceBot```')

	@commands.command(hidden=True)
	async def uptime(self, ctx):
		await ctx.send(f'`{str(datetime.now() - self.bot.startup_time).split(".")[0]}`')

	@commands.command(hidden=True)
	async def hello(self, ctx):
		await ctx.send(f'Hello {ctx.author.mention}!')

	@commands.command(hidden=True)
	async def shrug(self, ctx):
		await ctx.send('¯\_(ツ)_/¯')

	@commands.command(hidden=True)
	async def source(self, ctx):
		await ctx.send('https://github.com/Run1e/AceBot')


def setup(bot):
	bot.add_cog(Commands(bot))
