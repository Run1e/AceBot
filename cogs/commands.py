import discord, asyncio, random, inspect
from discord.ext import commands
from datetime import datetime

from config import wolfram_key, thecatapi_key, apixu_key, oxford_id, oxford_key


DISCORD_SIZE_LIMIT = 8 * 1024 * 1024 # 8MiB

class Commands:
	'''General command collection.'''
	
	query_error = commands.CommandError('Query failed. Try again later!')
	
	def __init__(self, bot):
		self.bot = bot
		
		with open('data/facts.txt', 'r', encoding='utf-8-sig') as f:
			self._facts = f.read().splitlines()
	
	@commands.command()
	async def fact(self, ctx):
		'''Get a random fact!'''
		
		await ctx.send(random.choice(self._facts))
	
	@commands.command()
	async def flip(self, ctx):
		'''Flip a coin!'''
		msg = await ctx.send('Flipping...')
		await asyncio.sleep(3)
		await msg.edit(content=random.choice(('Heads!', 'Tails!')))

	@commands.command(hidden=True)
	async def shrug(self, ctx):
		await ctx.send('¯\_(ツ)_/¯')

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

	@commands.command()
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def woof(self, ctx):
		'''Get a random doggo!'''
		
		url = 'https://random.dog/'
		params = {'filter': 'mp4'}
		
		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.request('get', url + 'woof', params=params) as resp:
					if resp.status != 200:
						raise self.query_error
					id = await resp.text()
				
				# fetch image using id
				async with self.bot.aiohttp.get(url + id) as resp:
					if resp.status != 200:
						raise self.query_error
					data = await resp.read()
			except asyncio.TimeoutError:
				raise self.query_error
				
		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		
		await ctx.send(file=discord.File(data, 'dog.' + resp.content_type.split('/')[-1]))
	
	@commands.command()
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def meow(self, ctx):
		'''Get a random cat image!'''
		
		url = 'http://thecatapi.com/api/images/get'
		params = {
			'format': 'src',
			'api_key': thecatapi_key
		}
		
		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get(url, params=params) as resp:
					if resp.status != 200:
						raise self.query_error
					data = await resp.read()
			except asyncio.TimeoutError:
				raise self.query_error
		
		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		
		await ctx.send(file=discord.File(data, 'cat.' + resp.content_type.split('/')[-1]))
	
	@commands.command()
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def quack(self, ctx):
		'''Get a random duck image!'''
		
		url = 'https://random-d.uk/api/v1/random'
		
		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get(url) as resp:
					if resp.status != 200:
						raise self.query_error
					json = await resp.json()
					image_url = json['url']
				
				async with self.bot.aiohttp.get(image_url) as resp:
					if resp.status != 200:
						raise self.query_error
					data = await resp.read()
			except asyncio.TimeoutError:
				raise self.query_error
		
		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		
		await ctx.send(file=discord.File(data, 'duck.' + resp.content_type.split('/')[-1]))
		
	@commands.command()
	async def floof(self, ctx):
		'''FLOOF'''
		
		url = 'https://randomfox.ca/floof/'
		
		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.request('get', url) as resp:
					if resp.status != 200:
						raise self.query_error
					json = await resp.json()
					image_url = json['image']
				
				async with self.bot.aiohttp.get(image_url) as resp:
					if resp.status != 200:
						raise self.query_error
					data = await resp.read()
			except asyncio.TimeoutError:
				raise self.query_error
			
		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		
		await ctx.send(file=discord.File(data, 'fix.' + resp.content_type.split('/')[-1]))
	
	@commands.command(aliases=['num'])
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
	
	@commands.command(aliases=['w'])
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def wolfram(self, ctx, *, query):
		'''Queries wolfram.'''
		
		params = {
			'appid': wolfram_key,
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
					
		text = f'Query:\n```{query}```\nResult:\n```{res}```'
		
		embed = discord.Embed(description=text)
		embed.set_author(name='Wolfram Alpha', icon_url='https://i.imgur.com/KFppH69.png')
		embed.set_footer(text='wolframalpha.com')
		
		if len(text) > 2000:
			raise commands.CommandError('Wolfram response too long.')
		
		await ctx.send(embed=embed)
		
	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command()
	async def weather(self, ctx, *, location: str = None):
		'''Check the weather at a location.'''

		if location is None:
			return await ctx.send('Please provide a location to get weather information for.')

		url = 'http://api.apixu.com/v1/current.json'

		params = {
			'key': apixu_key,
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
			
	@commands.command(name='8')
	async def ball(self, ctx, *, question):
		'''Classic Magic 8 Ball'''
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
		
	@commands.cooldown(rate=2, per=5.0, type=commands.BucketType.user)
	@commands.command(aliases=['def'])
	async def define(self, ctx, *, query):
		'''Define a word using Oxfords dictionary.'''

		await ctx.trigger_typing()

		url = 'https://od-api.oxforddictionaries.com:443/api/v1/entries/en/' + query.split('\n')[0].lower()

		headers = {
			'Accept': 'application/json',
			'app_id': oxford_id,
			'app_key': oxford_key
		}
		
		try:
			async with self.bot.aiohttp.get(url, headers=headers) as resp:
				if resp.status != 200:
					raise self.query_error
				info = await resp.json()
		except asyncio.TimeoutError:
			raise self.query_error

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
		
		
def setup(bot):
	bot.add_cog(Commands(bot))