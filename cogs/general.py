import discord
from discord.ext import commands

import asyncio
import random

from datetime import datetime

from config import WOLFRAM_KEY, APIXU_KEY, OXFORD_ID, OXFORD_KEY
from cogs.mixins import AceMixin


class General(AceMixin, commands.Cog):
	'''General commands.'''

	query_error = commands.CommandError('Query failed. Try again later.')

	@commands.command()
	async def flip(self, ctx):
		'''Flip a coin!'''

		msg = await ctx.send('\*flip\*')
		await asyncio.sleep(3)
		await msg.edit(content=random.choice(('Heads!', 'Tails!')))

	@commands.command()
	async def choose(self, ctx, *choices: commands.clean_content):
		'''Pick a random item from a list.'''

		if len(choices) < 2:
			raise commands.CommandError('At least two choices are necessary.')

		msg = await ctx.send(':thinking:...')
		await asyncio.sleep(3)
		await msg.edit(content=random.choice(choices))

	@commands.command()
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def number(self, ctx, number: int):
		'''Get a fact about a number!'''

		url = f'http://numbersapi.com/{number}?notfound=floor'

		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get(url) as resp:
					if resp.status != 200:
						raise self.query_error
					text = await resp.text()
			except asyncio.TimeoutError:
				raise self.query_error

		await ctx.send(text)

	@commands.command()
	async def fact(self, ctx):
		'''Get a random fact.'''

		fact = await self.db.fetchval('SELECT content FROM facts ORDER BY random()')

		print(fact)

		await ctx.send(fact)

	@commands.command(name='8', aliases=['8ball'])
	async def ball(self, ctx, *, question):
		'''Classic Magic 8 Ball!'''
		responses = (
			# yes
			'It is certain', 'It is decidedly so', 'Without a doubt', 'Yes definitely', 'You may rely on it',
			'As I see it, yes', 'Most likely', 'Outlook good', 'Yes',
			# uncertain
			'Signs point to yes', 'Reply hazy try again', 'Ask again later', 'Better not tell you now',
			'Cannot predict now', 'Concentrate and ask again',
			# no
			"Don't count on it", 'My reply is no', 'My sources say no', 'Outlook not so good', 'Very doubtful'
		)

		await ctx.trigger_typing()
		await asyncio.sleep(3)
		await ctx.send(random.choice(responses))

	@commands.command(aliases=['guild'])
	@commands.bot_has_permissions(embed_links=True)
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
		att['Online'] = (
			f'{sum(member.status is not discord.Status.offline for member in ctx.guild.members)}'
			f'/{len(ctx.guild.members)}'
		)

		att['Owner'] = ctx.guild.owner.mention
		att['Channels'] = len(ctx.guild.text_channels) + len(ctx.guild.voice_channels)
		att['Region'] = str(ctx.guild.region)
		att['Created at'] = str(ctx.guild.created_at).split(' ')[0]

		e = discord.Embed(title=ctx.guild.name, description='\n'.join(f'**{a}**: {b}' for a, b in att.items()))
		e.set_thumbnail(url=ctx.guild.icon_url)
		e.set_footer(text=f'ID: {ctx.guild.id}')
		e.add_field(name='Status', value='\n'.join(str(status) for status in statuses))
		e.add_field(name='Users', value='\n'.join(str(count) for status, count in statuses.items()))

		await ctx.send(embed=e)

	@commands.command(aliases=['w', 'wa'])
	@commands.bot_has_permissions(embed_links=True)
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def wolfram(self, ctx, *, query):
		'''Queries wolfram.'''

		if WOLFRAM_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		params = {
			'appid': WOLFRAM_KEY,
			'i': query
		}

		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get('https://api.wolframalpha.com/v1/result', params=params) as resp:
					if resp.status != 200:
						raise self.query_error

					res = await resp.text()
			except asyncio.TimeoutError:
				raise self.query_error

		embed = discord.Embed()

		query = query.replace('`', '\u200b`')

		embed.add_field(name='Query', value=f'```{query}```')
		embed.add_field(name='Result', value=f'```{res}```', inline=False)

		embed.set_author(name='Wolfram Alpha', icon_url='https://i.imgur.com/KFppH69.png')
		embed.set_footer(text='wolframalpha.com')

		if len(query) + len(res) > 1200:
			raise commands.CommandError('Wolfram response too long.')

		await ctx.send(embed=embed)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	async def weather(self, ctx, *, location: str):
		'''Check the weather at a location.'''

		if APIXU_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		url = 'http://api.apixu.com/v1/current.json'

		params = {
			'key': APIXU_KEY,
			'q': location
		}

		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get(url, params=params) as resp:
					if resp.status != 200:
						raise self.query_error
					data = await resp.json()
			except asyncio.TimeoutError:
				raise self.query_error

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

	# TODO: rewrite this literal clusterfuck
	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	async def define(self, ctx, *, word: str):
		'''Define a word using Oxfords dictionary.'''

		if OXFORD_ID is None or OXFORD_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		await ctx.trigger_typing()

		url = 'https://od-api.oxforddictionaries.com:443/api/v1/entries/en/' + word.split('\n')[0].lower()

		headers = {
			'Accept': 'application/json',
			'app_id': OXFORD_ID,
			'app_key': OXFORD_KEY
		}

		try:
			async with self.bot.aiohttp.get(url, headers=headers) as resp:
				if resp.status != 200:
					if resp.status == 404:
						raise commands.CommandError('Couldn\'t find a definition for that word.')
					else:
						raise self.query_error
				info = await resp.json()
		except asyncio.TimeoutError:
			raise self.query_error

		result = info['results'][0]

		lexentry = None
		for temp in result['lexicalEntries']:
			if lexentry is None:
				lexentry = temp
			try:
				temp['entries'][0]['senses'][0]['definitions']
				lexentry = temp
				break
			except KeyError:
				continue

		word = result['word']

		entry = lexentry['entries'][0]
		sense = entry['senses'][0]

		category = lexentry['lexicalCategory']

		e = discord.Embed(title=f'{word.title()} ({category})')

		if 'definitions' in sense:
			defin = sense['definitions'][0]
		elif 'short_definitions' in sense:
			defin = sense['short_definitions'][0]
		else:
			defin = 'No definition.'

		e.description = defin

		if 'examples' in sense:
			e.add_field(name='Example', value=sense['examples'][0]['text'])

		if 'grammaticalFeatures' in entry:
			e.add_field(
				name='Features',
				value=', '.join(temp['text'] for temp in entry['grammaticalFeatures']),
			)

		if 'registers' in sense:
			e.add_field(name='Registers', value=', '.join(sense['registers']))

		if 'domains' in sense:
			e.add_field(name='Domains', value=', '.join(sense['domains']))

		if 'regions' in sense:
			e.add_field(name='Regions', value=', '.join(sense['regions']))

		if 'pronunciations' in sense:
			pro = sense['pronunciations'][0]
			spelling = None
			if 'phoneticNotation' in pro:
				spelling = pro['phoneticNotation']
			elif 'proneticSpelling' in pro:
				spelling = pro['phoneticSpelling']

			if spelling is not None:
				if 'audioFile' in pro:
					spelling = f'[{spelling}]({pro["audioFile"]})'
				e.add_field(name='Pronunciation', value=spelling)

		if 'variantForms' in sense:
			e.add_field(name='Variants', value=', '.join(temp['text'] for temp in sense['variantForms']), inline=True)

		e.set_footer(text='Oxford University Press', icon_url='https://i.imgur.com/7GMY4dP.png')

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(General(bot))
