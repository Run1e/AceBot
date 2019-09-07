import discord
import asyncio
import aiohttp
import os
import logging
import io
import random

from discord.ext import commands

from config import THECATAPI_KEY
from cogs.mixins import AceMixin

DISCORD_SIZE_LIMIT = 8 * 1024 * 1024 # 8MiB
QUERY_ERROR = commands.CommandError('Query failed, try again later.')
MAX_ATTEMPTS = 3

log = logging.getLogger(__name__)


class FileTooLargeError(Exception):
	pass


class ImagePersister:

	_base_dir = 'data'

	def __init__(self, aiohttp, type):
		self.aiohttp = aiohttp
		self._type = type

		if not os.path.exists(self.path):
			os.makedirs(self.path)

	@property
	def path(self):
		return f'{self._base_dir}/{self._type}'

	async def request_text(self, url, params=None):
		data = await self.request(url, 'text', params)

		if len(data) > DISCORD_SIZE_LIMIT:
			raise FileTooLargeError()

		return data

	async def request_data(self, url, params=None):
		data = await self.request(url, 'read', params)

		if len(data) > DISCORD_SIZE_LIMIT:
			raise FileTooLargeError()

		return data

	async def request_json(self, url, params=None):
		data = await self.request(url, 'json', params)

		if len(data) > DISCORD_SIZE_LIMIT:
			raise FileTooLargeError()

		return data

	async def request(self, url, method, params=None):
		async with self.aiohttp.get(url, params=params) as resp:
			if resp.status != 200:
				raise QUERY_ERROR

			return await getattr(resp, method)()

	def fetch_if_exist(self, name):
		file = f'{self.path}/{name}'

		if not os.path.isfile(file):
			return None

		with open(file, 'rb') as f:
			return f.read()

	def store_image(self, name, data):
		with open(f'{self.path}/{name}', 'wb') as f:
			f.write(data)

	def get_random_image(self):
		try:
			file = random.choice(os.listdir(self.path))
		except IndexError:
			return None, None
		return file, self.fetch_if_exist(file)


class Image(AceMixin, commands.Cog):
	''':heart_eyes: :heart_eyes: :heart_eyes:'''

	QUERY_EXCEPTIONS = (aiohttp.ClientError, asyncio.TimeoutError, FileTooLargeError)
	EXCEPTION_FORMAT = 'Resorting to file system cache: {}'

	def __init__(self, bot):
		super().__init__(bot)

		self.woof_persister = ImagePersister(bot.aiohttp, 'dog')
		self.meow_persister = ImagePersister(bot.aiohttp, 'cat')
		self.floof_persister = ImagePersister(bot.aiohttp, 'fox')
		self.quack_persister = ImagePersister(bot.aiohttp, 'duck')

	@commands.command(aliases=['dog'])
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def woof(self, ctx):
		'''Get a random doggo!'''

		url = 'https://random.dog/'
		params = dict(filter='mp4')

		file = None
		data = None

		async with ctx.typing():
			try:
				file = await self.woof_persister.request_text(url + 'woof', params)
				data = self.woof_persister.fetch_if_exist(file)

				if data is None:
					data = await self.woof_persister.request_data(url + file)
					self.woof_persister.store_image(file, data)
			except self.QUERY_EXCEPTIONS as exc:
				log.warning(self.EXCEPTION_FORMAT.format(str(exc)))
				file, data = self.woof_persister.get_random_image()
			finally:
				if data is not None:
					await ctx.send(file=discord.File(io.BytesIO(data), file))
				else:
					raise QUERY_ERROR

	@commands.command(aliases=['cat'])
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def meow(self, ctx):
		'''Get a random cat image!'''

		if THECATAPI_KEY is None:
			raise commands.CommandError('The host has not set up an API key.')

		url = 'https://api.thecatapi.com/v1/images/search'
		params = dict(api_key=THECATAPI_KEY)

		file = None
		data = None

		async with ctx.typing():
			try:
				json = await self.meow_persister.request_json(url, params)

				img_url = json[0]['url']
				file = img_url.split('/')[-1]

				data = self.meow_persister.fetch_if_exist(file)

				if data is None:
					data = await self.meow_persister.request_data(img_url)
					self.meow_persister.store_image(file, data)

			except self.QUERY_EXCEPTIONS as exc:
				log.warning(self.EXCEPTION_FORMAT.format(str(exc)))
				file, data = self.meow_persister.get_random_image()
			finally:
				if data is not None:
					await ctx.send(file=discord.File(io.BytesIO(data), file))
				else:
					raise QUERY_ERROR

	@commands.command(aliases=['duck'])
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def quack(self, ctx):
		'''Get a random duck image!'''

		url = 'https://random-d.uk/api/v1/random'

		file = None
		data = None

		async with ctx.typing():
			try:
				json = await self.quack_persister.request_json(url)

				img_url = json['url']
				file = img_url.split('/')[-1]

				data = self.quack_persister.fetch_if_exist(file)

				if data is None:
					data = await self.quack_persister.request_data(img_url)
					self.quack_persister.store_image(file, data)
			except self.QUERY_EXCEPTIONS as exc:
				log.warning(self.EXCEPTION_FORMAT.format(str(exc)))
				file, data = self.quack_persister.get_random_image()
			finally:
				if data is not None:
					await ctx.send(file=discord.File(io.BytesIO(data), file))
				else:
					raise QUERY_ERROR

	@commands.command(aliases=['fox'])
	@commands.cooldown(rate=3, per=10.0, type=commands.BucketType.user)
	@commands.bot_has_permissions(attach_files=True)
	async def floof(self, ctx):
		'''~floooof~'''

		url = 'https://randomfox.ca/floof/'

		file = None
		data = None

		async with ctx.typing():
			try:
				json = await self.floof_persister.request_json(url)

				img_url = json['image']
				file = img_url.split('/')[-1]

				data = self.floof_persister.fetch_if_exist(file)

				if data is None:
					data = await self.floof_persister.request_data(img_url)
					self.floof_persister.store_image(file, data)
			except self.QUERY_EXCEPTIONS as exc:
				log.warning(self.EXCEPTION_FORMAT.format(str(exc)))
				file, data = self.floof_persister.get_random_image()
			finally:
				if data is not None:
					await ctx.send(file=discord.File(io.BytesIO(data), file))
				else:
					raise QUERY_ERROR


def setup(bot):
	bot.add_cog(Image(bot))
