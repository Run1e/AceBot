import asyncio
import logging
from datetime import date, datetime
from json import loads
from random import choice

import urllib.parse
import typing
import aiohttp
import bs4
import discord
from bs4 import BeautifulSoup
from fuzzywuzzy import fuzz, process
from discord.ext import commands, tasks

from cogs.mixins import AceMixin
from config import APIXU_KEY, THECATAPI_KEY, WOLFRAM_KEY
from utils.time import pretty_timedelta

QUERY_ERROR = commands.CommandError('Query failed, try again later.')

WOOF_URL = 'https://random.dog/'
WOOF_HEADERS = dict(filter='mp4')

MEOW_URL = 'https://api.thecatapi.com/v1/images/search'
MEOW_HEADERS = {'x-api-key': THECATAPI_KEY}
MEOW_BREEDS = [
	'abys', 'aege', 'abob', 'acur', 'asho', 'awir', 'amau', 'amis', 'bali', 'bamb', 'beng', 'birm', 'bomb', 'bslo', 'bsho', 'bure', 'buri', 'cspa',
	'ctif', 'char', 'chau', 'chee', 'csho', 'crex', 'cymr', 'cypr', 'drex', 'dons', 'lihu', 'emau', 'ebur', 'esho', 'hbro', 'hima', 'jbob', 'java',
	'khao', 'kora', 'kuri', 'lape', 'mcoo', 'mala', 'manx', 'munc', 'nebe', 'norw', 'ocic', 'orie', 'pers', 'pixi', 'raga', 'ragd', 'rblu', 'sava',
	'sfol', 'srex', 'siam', 'sibe', 'sing', 'snow', 'soma', 'sphy', 'tonk', 'toyg', 'tang', 'tvan', 'ycho'
]

QUACK_URL = 'https://random-d.uk/api/v1/random'

FLOOF_URL = 'https://randomfox.ca/floof/'

COMPLIMENT_URL = 'https://complimentr.com/api'
COMPLIMENT_EMOJIS = ('heart', 'kissing_heart', 'heart_eyes', 'two_hearts', 'sparkling_heart', 'gift_heart')

NUMBER_URL = 'http://numbersapi.com/{number}?notfound=floor'

BILL_WURTZ_URL = 'https://billwurtz.com/'

BILL_CACHE = {'videos': None, 'songs': None, 'instrumentals': None}

BALL_RESPONSES = [
	# yes
	'It is certain', 'It is decidedly so', 'Without a doubt', 'Yes definitely', 'You may rely on it',
	'As I see it, yes', 'Most likely', 'Outlook good', 'Yes',
	# uncertain
	'Signs point to yes', 'Reply hazy try again', 'Ask again later', 'Better not tell you now',
	'Cannot predict now', 'Concentrate and ask again',
	# no
	"Don't count on it", 'My reply is no', 'My sources say no', 'Outlook not so good', 'Very doubtful'
]

QUERY_EXCEPTIONS = (discord.HTTPException, aiohttp.ClientError, asyncio.TimeoutError, commands.CommandError)

log = logging.getLogger(__name__)


class Fun(AceMixin, commands.Cog):
	'''Fun commands!'''

	def __init__(self, bot):
		self.bot = bot
		self.cache_bill_vids.start()
	
	def cog_unload(self):
		self.cache_bill_vids.cancel()

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def server(self, ctx):
		"""Show various information about the server."""

		guild = ctx.guild

		desc = dict(
			ID=guild.id,
		)

		e = discord.Embed(
			title=guild.name,
			description='\n'.join('**{}**: {}'.format(key, value) for key, value in desc.items()),
			timestamp=guild.created_at
		)

		e.add_field(
			name='Owner',
			value=guild.owner.mention
		)

		e.add_field(
			name='Region',
			value=str(guild.region)
		)

		# CHANNELS

		channels = {
			discord.TextChannel: 0,
			discord.VoiceChannel: 0,
		}

		for channel in guild.channels:
			for channel_type in channels:
				if isinstance(channel, channel_type):
					channels[channel_type] += 1

		channel_desc = '{} {}\n{} {}'.format(
			'<:text_channel:635021087247171584>',
			channels[discord.TextChannel],
			'<:voice_channel:635021113134546944>',
			channels[discord.VoiceChannel]
		)

		e.add_field(
			name='Channels',
			value=channel_desc
		)

		# FEATURES

		if guild.features:
			e.add_field(
				name='Features',
				value='\n'.join('• ' + feature.replace('_', ' ').title() for feature in guild.features)
			)

		# MEMBERS

		statuses = dict(
			online=0,
			idle=0,
			dnd=0,
			offline=0
		)

		total_online = 0

		for member in guild.members:
			status_str = str(member.status)
			if status_str != "offline":
				total_online += 1
			statuses[status_str] += 1

		member_desc = '{} {} {} {} {} {} {} {}'.format(
			'<:online:635022092903120906>',
			statuses['online'],
			'<:idle:635022068290813952>',
			statuses['idle'],
			'<:dnd:635022045952081941>',
			statuses['dnd'],
			'<:offline:635022116462264320>',
			statuses['offline']
		)

		e.add_field(
			name='Members ({}/{})'.format(total_online, len(guild.members)),
			value=member_desc, inline=False
		)

		# SERVER BOOST

		boost_desc = 'Level {} - {} Boosts'.format(guild.premium_tier, guild.premium_subscription_count)

		if guild.premium_subscribers:
			# actually get the last premium subscriber. this list is always fucked
			booster = sorted(guild.premium_subscribers, key=lambda m: m.premium_since)[-1]
			boost_desc += '\nLast boost by {} {} ago'.format(
				booster.mention, pretty_timedelta(datetime.utcnow() - booster.premium_since)
			)

		e.add_field(
			name='Server boost',
			value=boost_desc
		)

		e.set_thumbnail(url=guild.icon_url)
		e.set_footer(text='Created')

		await ctx.send(embed=e)

	@commands.command(aliases=['w', 'wa'])
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def wolfram(self, ctx, *, query):
		'''Run Wolfram Alpha queries from Discord!'''

		if WOLFRAM_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		params = {
			'appid': WOLFRAM_KEY,
			'input': query,
			'output': 'json',
			'ip': '',
			'units': 'metric',
			'format': 'plaintext',
			'podindex': '1,2,3'
		}

		headers = {
			'Content-Type': 'application/json'
		}

		async with ctx.channel.typing():
			try:
				cntx = ctx.http.get('https://api.wolframalpha.com/v2/query', params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=20))
				async with cntx as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					j = await resp.text()
			except asyncio.TimeoutError:
				raise QUERY_ERROR

			log.debug(resp.url)

			j = loads(j)
			res = j['queryresult']

			success = res['success'] and res['numpods']

			e = discord.Embed(color=0xFF6600)
			e.set_author(name='Wolfram|Alpha', icon_url='https://i.imgur.com/KFppH69.png')
			e.set_footer(text='wolframalpha.com')

			if not success:
				e.description = 'Sorry, Wolfram Alpha was not able to parse your request.'
				means = res.get('didyoumeans', None)

				if means is not None:
					val = ', '.join(x['val'] for x in means) if isinstance(means, list) else means['val']
					e.add_field(name='Wolfram is having issues with these word(s):', value='```{0}```'.format(val), inline=False)

				if 'tips' in res:
					e.add_field(name='Tips from Wolfram Alpha:', value=res['tips']['text'], inline=False)

				if not e.fields and not res['numpods']:
					e.add_field(
						name='Possible reason:',
						value=(
							'It is possible this failed due to not providing a location.\n'
							'Try providing a location within your query.'),
						inline=False
					)

				await ctx.send(embed=e)
				return

			has_image = False
			for idx, pod in enumerate(res['pods']):
				name = pod['title']
				_id = pod['id']
				subpods = pod['subpods']

				if _id.startswith('Image'):
					if has_image:
						continue

					has_image = True

					imagesource = subpods[0]['imagesource']

					if 'en.wikipedia.org/wiki/File:' in imagesource:
						commons_image = await self.unpack_commons_image(ctx.http, imagesource)

						if commons_image is not None:
							e.set_image(url=commons_image)
					else:
						e.set_image(url=imagesource)

					continue

				if len(e.fields) > 2:
					continue

				if _id == 'Input':
					plaintext = subpods[0]['plaintext']
					value = plaintext.replace('\n', ' ').replace('  ', ' ')
				else:
					value = []
					for subpod in subpods:
						plaintext = subpod['plaintext']
						if plaintext:
							value.append(plaintext)

					value = '\n'.join(value)

				if value:
					wraps = '`' if _id == 'Input' else '```'
					e.add_field(name=name, value='{0}{1}{0}'.format(wraps, value), inline=False)

			await ctx.send(embed=e)

	@commands.command()
	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def weather(self, ctx, *, location: str):
		'''Check the weather at a location.'''

		if APIXU_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		url = 'http://api.weatherstack.com/current'

		params = {
			'access_key': APIXU_KEY,
			'query': location
		}

		async with ctx.channel.typing():
			try:
				async with ctx.http.get(url, params=params) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					data = await resp.json()
			except asyncio.TimeoutError:
				raise QUERY_ERROR

			if data.get('success', True) is False:
				raise commands.CommandError('Unable to find a location match.')

			location = data['location']
			current = data['current']

			observation_time = datetime.strptime(current['observation_time'], '%I:%M %p').time()

			e = discord.Embed(
				title='Weather for {}, {} {}'.format(location['name'], location['region'], location['country'].upper()),
				description='*{}*'.format(' / '.join(current["weather_descriptions"])),
				timestamp=datetime.combine(date.today(), observation_time),
			)

			e.set_footer(text='Observed')

			if current['weather_icons']:
				e.set_thumbnail(url=current['weather_icons'][0])

			e.add_field(name='Temperature', value='{}°C'.format(current['temperature']))
			e.add_field(name='Feels Like', value='{}°C'.format(current['feelslike']))
			e.add_field(name='Precipitation', value='{} mm'.format(current['precip']))
			e.add_field(name='Humidity', value='{}%'.format(current['humidity']))
			e.add_field(name='Wind Speed', value='{} kph'.format(current['wind_speed']))
			e.add_field(name='Wind Direction', value=current['wind_dir'])

			await ctx.send(embed=e)

	def _create_embed(self, url=None):
		e = discord.Embed(color=0x36393E)
		if url is not None:
			e.set_image(url=url)
		log.info(url)
		return e

	@commands.command(name='8', aliases=['8ball'])
	async def ball(self, ctx, *, question):
		'''Ask the Magic 8 Ball anything!'''

		message = await ctx.send('Shaking...')
		await asyncio.sleep(3)
		await message.edit(content='\N{BILLIARDS} ' + choice(BALL_RESPONSES))

	@commands.command()
	async def flip(self, ctx):
		'''Flip a coin!'''

		msg = await ctx.send('*Flipping...*')
		await asyncio.sleep(3)
		await msg.edit(content=choice(('Heads!', 'Tails!')))

	@commands.command()
	async def choose(self, ctx, *choices: commands.clean_content):
		'''Pick a random item from a list separated by spaces.'''

		choose_prompts = (
			'I have chosen',
			'I have a great feeling about',
			'I\'ve decided on',
			'Easy choice',
			'I think',
		)

		if len(choices) < 2:
			raise commands.CommandError('At least two choices are necessary.')

		selected = choice(choices)

		e = discord.Embed(
			description=selected
		)

		e.set_author(name=choice(choose_prompts) + ':', icon_url=self.bot.user.avatar_url)

		msg = await ctx.send(':thinking:')

		await asyncio.sleep(3)
		await msg.edit(content=None, embed=e)

	@commands.command()
	async def fact(self, ctx):
		'''Get a random fact.'''

		fact = await self.db.fetchrow('SELECT * FROM facts ORDER BY random()')

		e = discord.Embed(
			title='Fact #{}'.format(fact.get('id')),
			description=fact.get('content')
		)

		await ctx.send(embed=e)

	async def unpack_commons_image(self, http, url):
		try:
			async with http.get(url) as resp:
				if resp.status != 200:
					return None

				bs = BeautifulSoup(await resp.text(), 'html.parser')
				tag = bs.find('a', class_='internal', href=True)

				if tag is not None:
					href = tag.get('href')
					if not href.startswith('http'):
						href = 'https:' + href
					return href
			return None
		except TimeoutError:
			return None

	@tasks.loop(hours=1.0)
	async def cache_bill_vids(self):
		'''Requests the bill videos from the website. 
		Caching is done in order to speed up searching'''
		
		for key in BILL_CACHE.keys():
			BILL_CACHE[key] = await self.get_bill_soup(file=key, use_cache=False)
	

	async def get_bill_soup(self, *, file: str = "videos.html", use_cache=True):
		"""Get bill videos/songs and return the beautifulsoup object"""

		if file.endswith('.html'):
			file = file.rstrip('.html')

		if use_cache and BILL_CACHE[file] is not None:
			return BILL_CACHE[file]

		async with self.bot.aiohttp.get(BILL_WURTZ_URL + file + '.html') as resp:
			if resp.status != 200:
				raise commands.CommandError('Request failed.')
			content = await resp.text()
		
		soup = BeautifulSoup(content, 'lxml')

		def bill_filter(el):
			# needs to have 2 td children
			names = [c.name for c in el.children if c.name is not None]
			return len(names)==2 and all(name=="td" for name in names)

		tokens = [(toke if getattr(toke,'a', None) is not None else None) for toke in soup.find_all(bill_filter)]
		
		while tokens.count(None) > 0:
			tokens.remove(None)

		BILL_CACHE[file] = tokens
		
		return tokens

	def get_bill_file(self, query, title, fuzzed_threshold=89):
		"""
		Take a query and fuzzy match it to titles list and return it
		if it matches above the threshold.
		"""
		fuzzed = process.extractOne(query, title)

		log.debug("bill query fuzzed: " + str(fuzzed))

		if fuzzed[-1] < fuzzed_threshold:
			return (False, fuzzed)

		return (True, fuzzed)


	@commands.command(aliases=('wurtz',))
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def bill(self, ctx, *, query: str = None):
		'''Get a random Bill Wurtz video from his website, with optional search.'''

		file = 'videos'
		if query and query.split(' ')[0] in BILL_CACHE.keys():
			file = query.split(' ')[0]
			query = ' '.join(query.split(' ')[1:])

			if query == '':
				query = None
	
		log.debug('query: ' + (query or "None"))
		log.debug('file: ' + (file or "None"))

		async with ctx.typing():
			soup = await self.get_bill_soup(file=file, use_cache=not (query or '').lower().startswith('latest'))

			tag: bs4.Tag = None

			if query is None:
				tag = choice(soup)

			elif query.startswith('latest'):
				query: str = soup[0]('a')[0].string

			else:
				accept, query = self.get_bill_file(query, [tag('a')[0].string for tag in soup])
				
				if not accept:
					raise commands.CommandError(
							"Couldn't match that search with certainty.\n"
							f"Closest match: '{query[0].strip()}'"
						)

				query = query[0]

			for v in soup:
				if query == v('a')[0].string:
					tag = v
					break
			
			bill_date = tag('td')[0].string.strip().split('.')
			bill_date = (
				'20' + bill_date[2], 
				bill_date[0].rjust(2,'0'), 
				bill_date[1].rjust(2, '0')
			)
			bill_date = [int(x) for x in bill_date]
			bill_date = date(*bill_date).strftime('%B %d, %Y')

			tag = tag('a')[0]

		await ctx.send(
			f"{bill_date}: "
			f"*{discord.utils.escape_markdown(tag.string.strip())}* \n"
			f"{BILL_WURTZ_URL + tag['href']}"
		)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def xkcd(self, ctx, *, search: typing.Union[int, str] = None):
		'''Get an xkcd comic. Search can be `latest`, a comic id, a search string, or nothing for a random comic.'''

		async with ctx.typing():
			if search is None:
				await self.random(ctx)
			elif isinstance(search, int):
				await self.num(ctx, search)
			elif search == 'latest':
				await self.latest(ctx)
			else:
				await self.search(ctx, search=search)

	async def num(self, ctx, id: int):
		'''Get a specific xkcd comic, given a number.'''

		e = await self.get_xkcd_comic(ctx, id)
		await ctx.send(embed=e)

	async def latest(self, ctx):
		'''Get the latest xkcd comic.'''

		url = 'https://xkcd.com/info.0.json'

		comic_json = await self.get_xkcd_json(url)
		e = self.make_xkcd_embed(comic_json)

		await ctx.send(embed=e)

	async def random(self, ctx):
		'''Get a random xkcd comic.'''

		url = 'https://c.xkcd.com/random/comic/'

		async with ctx.http.get(url) as resp:
			if resp.status != 200:
				raise commands.CommandError('Request failed.')
			num = str(resp.url).lstrip('https://xkcd.com/').rstrip('/')

		url = 'https://xkcd.com/{}/info.0.json'.format(num)
		comic_json = await self.get_xkcd_json(url)
		e = self.make_xkcd_embed(comic_json)

		await ctx.send(embed=e)

	async def search(self, ctx, *, search: str):
		'''Get a relevant xkcd from [`relevantxkcd.appspot.com`](https://relevantxkcd.appspot.com).'''

		relevant_xkcd_url = 'https://relevantxkcd.appspot.com/process?action=xkcd&query='
		search_url = relevant_xkcd_url + urllib.parse.quote(search)

		async with ctx.http.get(search_url) as resp:
			text = await resp.text()
			results = text.split('\n')
			num = results[2].split(' ')[0]

			e = await self.get_xkcd_comic(ctx, num)

			more_results = f'[More results]({search_url})'
			relevance = '**Relevancy:** {}%\n{}\n\n'.format(str(round(float(results[0]) * 100, 2)), more_results)
			e.description = relevance + e.description

			await ctx.send(embed=e)

	async def get_xkcd_comic(self, ctx, id):
		url = f'https://xkcd.com/{id}/info.0.json'
		async with ctx.http.get(url) as resp:
			if resp.status != 200:
				raise commands.CommandError('Request failed.')
			comic_json = await resp.json()
		e = self.make_xkcd_embed(comic_json)
		return e

	async def get_xkcd_json(self, url):
		async with self.bot.aiohttp.get(url) as resp:
			if resp.status == 404:
				raise commands.CommandError('Comic does not exist.')
			if resp.status != 200:
				raise commands.CommandError('Request failed.')
			return await resp.json()

	def make_xkcd_embed(self, comic_json):
		comic_url = 'https://xkcd.com/{}'.format(comic_json['num'])
		e = discord.Embed(
			title=comic_json['title'],
			url=comic_url,
			description='{}'.format(comic_json['alt'])
		)
		comic_date = date(int(comic_json['year']), int(comic_json['month']), int(comic_json['day']))
		footer_text = 'xkcd.com/{}  •  {}'.format(comic_json['num'], comic_date)
		e.set_image(url=comic_json['img'])
		e.set_footer(text=footer_text, icon_url='https://i.imgur.com/onzWnfd.png')
		return e

	@commands.command(aliases=['dog'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def woof(self, ctx):
		'''Get a random doggo image!'''

		async with ctx.typing():
			try:
				async with ctx.http.get(WOOF_URL + 'woof', params=WOOF_HEADERS) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					file = await resp.text()

				if file.lower().endswith('.webm'):
					log.info('woof got webm, reinvoking...')
					await ctx.reinvoke()
					return

				await ctx.send(WOOF_URL + file)
			except QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command(aliases=['cat'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def meow(self, ctx):
		'''Get a random cat image!'''

		if THECATAPI_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		async with ctx.typing():
			try:
				async with ctx.http.get(MEOW_URL, headers=MEOW_HEADERS) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				data = json[0]
				img_url = data['url']

				await ctx.send(img_url)
			except QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command(aliases=['duck'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def quack(self, ctx):
		'''Get a random duck image!'''

		async with ctx.typing():
			try:
				async with ctx.http.get(QUACK_URL) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				img_url = json['url']

				await ctx.send(img_url)
			except QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command(aliases=['fox'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def floof(self, ctx):
		'''~floooof~'''

		async with ctx.typing():
			try:
				async with ctx.http.get(FLOOF_URL) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				img_url = json['image']

				await ctx.send(img_url)
			except QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command()
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(embed_links=True)
	async def breed(self, ctx):
		'''Get information on a random cat breed!'''

		if THECATAPI_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		async with ctx.typing():
			try:
				async with ctx.http.get(MEOW_URL, params=dict(breed_ids=choice(MEOW_BREEDS)), headers=MEOW_HEADERS) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				data = json[0]

				img_url = data['url']

				e = self._create_embed(img_url)

				breed = data['breeds'][0]

				e.set_author(name=breed['name'], url=breed.get('wikipedia_url', None))
				e.description = breed['description']

				e.add_field(name='Origin', value=breed['origin'])
				e.add_field(name='Weight', value=breed['weight']['metric'] + ' kg')
				e.add_field(name='Life span', value=breed['life_span'] + ' years')

				await ctx.send(embed=e)
			except QUERY_EXCEPTIONS:
				raise QUERY_ERROR


def setup(bot):
	bot.add_cog(Fun(bot))
