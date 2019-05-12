import discord, asyncio, os, logging
from discord.ext import commands

from config import THECATAPI_KEY

log = logging.getLogger(__name__)

DISCORD_SIZE_LIMIT = 8 * 1024 * 1024  # 8MiB

BASE_DIR = 'data'


async def put_image(type, file, data):
	dir = f'{BASE_DIR}/{type}'

	if not os.path.isdir(dir):
		os.makedirs(dir)

	with open(f'{dir}/{file}', 'wb') as f:
		f.write(data)


async def get_image(type, file):
	file = f'{BASE_DIR}/{type}/{file}'

	if not os.path.isfile(file):
		return None

	with open(file, 'rb') as f:
		return f.read()


class Image:
	''':heart_eyes: :heart_eyes: :heart_eyes:'''

	query_error = commands.CommandError('Query failed. Try again later!')

	def __init__(self, bot):
		self.bot = bot

	@commands.command(aliases=['dog'])
	@commands.bot_has_permissions(attach_files=True)
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

				data = await get_image('dogs', id)

				if data is None:
					# fetch image using id
					async with self.bot.aiohttp.get(url + id) as resp:
						if resp.status != 200:
							raise self.query_error
						data = await resp.read()
						await put_image('dogs', id, data)
				else:
					log.info(f'Found {id} in dogs cache!')

			except asyncio.TimeoutError:
				raise self.query_error

		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		else:
			await ctx.send(file=discord.File(data, id))

	@commands.command(aliases=['cat'])
	@commands.bot_has_permissions(attach_files=True)
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	async def meow(self, ctx):
		'''Get a random cat image!'''

		if THECATAPI_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		url = 'https://api.thecatapi.com/v1/images/search'
		params = {
			'api_key': THECATAPI_KEY
		}

		async with ctx.channel.typing():
			try:
				async with self.bot.aiohttp.get(url, params=params) as resp:
					if resp.status != 200:
						raise self.query_error
					js = await resp.json()
					image_url = js[0]['url']

				filename = image_url.split('/')[-1]

				data = await get_image('cats', filename)

				if data is None:
					async with self.bot.aiohttp.get(image_url) as resp:
						if resp.status != 200:
							raise self.query_error
						data = await resp.read()
						await put_image('cats', filename, data)

			except asyncio.TimeoutError:
				raise self.query_error

		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		else:
			await ctx.send(file=discord.File(data, filename))

	@commands.command(aliases=['duck'])
	@commands.bot_has_permissions(attach_files=True)
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

				filename = image_url.split('/')[-1]
				data = await get_image('ducks', filename)

				if data is None:
					async with self.bot.aiohttp.get(image_url) as resp:
						if resp.status != 200:
							raise self.query_error
						data = await resp.read()
						await put_image('ducks', filename, data)

			except asyncio.TimeoutError:
				raise self.query_error

		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		else:
			await ctx.send(file=discord.File(data, filename))

	@commands.command(aliases=['fox'])
	@commands.bot_has_permissions(attach_files=True)
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
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

				filename = image_url.split('/')[-1]

				data = await get_image('foxes', filename)

				if data is None:
					async with self.bot.aiohttp.get(image_url) as resp:
						if resp.status != 200:
							raise self.query_error
						data = await resp.read()
						await put_image('foxes', filename, data)

			except asyncio.TimeoutError:
				raise self.query_error

		if len(data) > DISCORD_SIZE_LIMIT:
			await ctx.reinvoke()
		else:
			await ctx.send(file=discord.File(data, filename))


def setup(bot):
	bot.add_cog(Image(bot))
