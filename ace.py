import discord
from discord.ext import commands

import asyncpg
import aiohttp
import traceback
import io
import logging
import logging.handlers
import sys
import os

from datetime import datetime

from config import *
from utils.time import pretty_seconds

DESCRIPTION = '''
A.C.E. - Autonomous Command Executor

Written and maintained by RUNIE 🔥#9646
Contributions: Vinter Borge, Cap'n Odin#8812, and GeekDude#2532
'''

EXTENSIONS = (
	'cogs.general',
	'cogs.stars',
	'cogs.seen',
)

class AceBot(commands.Bot):
	_support_link = 'https://discord.gg/X7abzRe'
	_prefixes = dict()
	_modules = dict()

	def __init__(self):
		log.info('Starting...')

		super().__init__(
			command_prefix=self.prefix_resolver,
			owner_id=OWNER_ID,
			description=DESCRIPTION
		)

		# do blacklist check before all commands
		self.add_check(self.blacklist, call_once=True)

	async def on_connect(self):
		'''Called on connection with the Discord gateway.'''

		log.info('Connected to Discord...')

	async def on_ready(self):
		'''Called when discord.py has finished connecting to the gateway.'''

		if not hasattr(self, 'db'):
			log.info('Creating database connection...')

			self.db = await asyncpg.create_pool(DB_BIND)

		if not hasattr(self, 'aiohttp'):
			log.info('Initializing aiohttp')
			self.aiohttp = aiohttp.ClientSession(
				loop=self.loop,
				timeout=aiohttp.ClientTimeout(total=5)
			)

		for extension in EXTENSIONS:
			print(f'loading {extension}')
			self.load_extension(extension)


	async def on_resumed(self):
		log.info('Bot resumed...')

	async def on_guild_unavailable(self, guild):
		log.info(f'Guild "{guild.name}" unavailable')

	def invalidate_guild_modules(self, guild_id):
		'''Remove a guilds modules from the module cache.'''

		if guild_id in self._modules:
			self._modules.pop(guild_id)

	@property
	def invite_link(self, perms=None):
		if perms is None:
			perms = 67497025
		return f'https://discordapp.com/oauth2/authorize?&client_id={self.user.id}&scope=bot&permissions={perms}'

	def invalidate_guild_prefix(self, guild_id):
		'''Remove a guilds prefix from the prefix cache.'''

		if guild_id in self._prefixes:
			self._prefixes.pop(guild_id)

	async def guild_uses_module(self, guild_id, module):
		if guild_id in self._modules and module in self._modules[guild_id]:
			return True

		if guild_id not in self._modules:
			self._modules[guild_id] = dict()

		value = await self.db.fetchval('SELECT id FROM module WHERE guild_id=$1 AND module=$2', guild_id, module)

		self._modules[guild_id][module] = False if value is None else True

		return self._modules[guild_id][module]

	async def prefix_resolver(self, bot, message):
		if message.guild.id in self._prefixes:
			return self._prefixes[message.guild.id]

		prefix = await self.db.fetchval('SELECT prefix FROM prefix WHERE guild_id = $1', message.guild.id) or DEFAULT_PREFIX

		self._prefixes[message.guild.id] = prefix

		return prefix

	async def blacklist(self, ctx):
		if ctx.guild is None:
			return False

		if ctx.author.bot:
			return False

		return True

	async def on_command_error(self, ctx, exc):

		log.info(str(exc))

		e = discord.Embed()

		async def log_and_raise():
			e.description = 'An error occured. The exception has been logged and will hopefully be fixed. Thanks for using the bot!'
			await ctx.send(embed=e)

			try:
				raise exc
			except Exception:
				log.exception(f'Unhandled command error:')
				raise exc

		if isinstance(exc, commands.CommandInvokeError):
			exc = exc.original
			await log_and_raise()

		if isinstance(exc, (commands.ConversionError, commands.UserInputError)):
			e.description = f'Usage: `{self.command_prefix}{ctx.command.signature}`'

		elif isinstance(exc, commands.DisabledCommand):
			e.description = 'Sorry, command has been disabled by owner. Try again later!'

		elif isinstance(exc, commands.CommandOnCooldown):
			e.title = 'You are on cooldown.'
			e.description = f'Try again in {pretty_seconds(exc.retry_after)}'

		elif isinstance(exc, commands.BotMissingPermissions):
			e.title = 'Bot is missing permissions to run command:'
			e.description = ', '.join(perm.replace('_', ' ').title() for perm in exc.missing_perms)

		elif isinstance(exc, (commands.CheckFailure, commands.CommandNotFound)):
			return # specifically do nothing on these

		elif isinstance(exc, commands.CommandError):
			e.description = str(exc)

		elif isinstance(exc, discord.DiscordException):
			await log_and_raise()

		await ctx.send(embed=e)

# monkey-patched Embed class to force embed color
class Embed(discord.Embed):
	def __init__(self, color=0x2E4D83, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)


discord.Embed = Embed

if __name__ == '__main__':

	# create additional folders
	for path in ('logs', 'temp'):
		if not os.path.exists(path):
			os.makedirs(path)

	# init first log file
	if not os.path.isfile('logs/log.log'):
		open('logs/log.log', 'w+')

	# set logging levels for discord and gino lib
	logging.getLogger('discord').setLevel(logging.INFO)

	# we want out logging formatted like this everywhere
	fmt = logging.Formatter('[{asctime}] [{levelname}] {name}: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{')

	level = getattr(logging, LOG_LEVEL)

	# this is the standard output stream
	stream = logging.StreamHandler(sys.stdout)
	stream.setLevel(level)
	stream.setFormatter(fmt)

	# this is the rotating file logger
	file = logging.handlers.TimedRotatingFileHandler('logs/log.log', when='midnight', encoding='utf-8-sig')
	file.setLevel(level)
	file.setFormatter(fmt)

	# get the root logger and add handlers
	log = logging.getLogger()
	log.setLevel(level)
	log.addHandler(stream)
	log.addHandler(file)

	# start the bot
	AceBot().run(BOT_TOKEN)
