import discord
import asyncio
import aiohttp
import logging

from discord.ext import commands

from config import THECATAPI_KEY
from cogs.mixins import AceMixin

QUERY_ERROR = commands.CommandError('Query failed, try again later.')

QUOTES = (
	'That\'s the cutest thing I\'ve ever seen.',
	'OMG :heart_eyes:',
	'I didn\'t know they came in this level of cute.',
	':heart_eyes: :heart_eyes: :heart_eyes:',
	'CUTE ASF.',
	'I wanna hug it so bad.',
)

WOOF_URL = 'https://random.dog/'
WOOF_HEADERS = dict(filter='mp4')
MEOW_URL = 'https://api.thecatapi.com/v1/images/search'
MEOW_HEADERS = dict(api_key=THECATAPI_KEY)
QUACK_URL = 'https://random-d.uk/api/v1/random'
FLOOF_URL = 'https://randomfox.ca/floof/'


log = logging.getLogger(__name__)


class Image(AceMixin, commands.Cog):
	''':heart_eyes: :heart_eyes: :heart_eyes:'''

	QUERY_EXCEPTIONS = (discord.HTTPException, aiohttp.ClientError, asyncio.TimeoutError, QUERY_ERROR)
	EXCEPTION_FORMAT = 'Resorting to file system cache: {}'

	def __init__(self, bot):
		super().__init__(bot)

	def _create_embed(self, url=None):
		e = discord.Embed() # description=choice(QUOTES))
		if url is not None:
			e.set_image(url=url)
		log.info(url)
		return e

	@commands.command(aliases=['dog'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def woof(self, ctx):
		'''Get a random doggo!'''

		async with ctx.typing():
			try:
				async with self.aiohttp.get(WOOF_URL + 'woof', params=WOOF_HEADERS) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					file = await resp.text()

				e = self._create_embed(WOOF_URL + file)
				await ctx.send(embed=e)
			except self.QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command(aliases=['cat'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def meow(self, ctx):
		'''Get a random cat image!'''

		if THECATAPI_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		async with ctx.typing():
			try:
				async with self.aiohttp.get(MEOW_URL, params=MEOW_HEADERS) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				img_url = json[0]['url']

				e = self._create_embed(img_url)
				await ctx.send(embed=e)
			except self.QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command(aliases=['duck'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def quack(self, ctx):
		'''Get a random duck image!'''

		async with ctx.typing():
			try:
				async with self.aiohttp.get(QUACK_URL,) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				img_url = json['url']

				e = self._create_embed(img_url)
				await ctx.send(embed=e)
			except self.QUERY_EXCEPTIONS:
				raise QUERY_ERROR

	@commands.command(aliases=['fox'])
	@commands.cooldown(rate=6, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def floof(self, ctx):
		'''~floooof~'''

		async with ctx.typing():
			try:
				async with self.aiohttp.get(FLOOF_URL) as resp:
					if resp.status != 200:
						raise QUERY_ERROR
					json = await resp.json()

				img_url = json['image']

				e = self._create_embed(img_url)
				await ctx.send(embed=e)
			except self.QUERY_EXCEPTIONS:
				raise QUERY_ERROR


def setup(bot):
	bot.add_cog(Image(bot))
