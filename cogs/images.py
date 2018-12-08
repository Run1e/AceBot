import discord, asyncio
from discord.ext import commands

from config import thecatapi_key

DISCORD_SIZE_LIMIT = 8 * 1024 * 1024  # 8MiB


class Image:
	''':heart_eyes: :heart_eyes: :heart_eyes:'''

	query_error = commands.CommandError('Query failed. Try again later!')

	def __init__(self, bot):
		self.bot = bot

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
		'''~floooof~'''

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

		await ctx.send(file=discord.File(data, 'fox.' + resp.content_type.split('/')[-1]))


def setup(bot):
	bot.add_cog(Image(bot))
