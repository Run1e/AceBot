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
from cogs.help import Help
from utils.time import pretty_seconds
from utils.guildconfig import GuildConfig

EXTENSIONS = (
	'cogs.owner',
	'cogs.general',
	'cogs.configuration',
	'cogs.stars',
	'cogs.seen',
	'cogs.security',
	'cogs.hl'
)

class AceBot(commands.Bot):
	_support_link = 'https://discord.gg/X7abzRe'

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

		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_ready(self):
		'''Called when discord.py has finished connecting to the gateway.'''

		self.help_command = Help()

		if not hasattr(self, 'db'):
			log.info('Creating database connection...')

			self.db = await asyncpg.create_pool(DB_BIND)

			GuildConfig.set_bot(self)

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
		await self.on_connect()

	async def on_guild_unavailable(self, guild):
		log.info(f'Guild "{guild.name}" unavailable')

	@property
	def invite_link(self, perms=None):
		if perms is None:
			perms = 67497025
		return f'https://discordapp.com/oauth2/authorize?&client_id={self.user.id}&scope=bot&permissions={perms}'

	async def guild_uses_module(self, guild_id, module):
		guild = await GuildConfig.get_guild(guild_id)
		return await guild.uses_module(module)

	async def prefix_resolver(self, bot, message):
		guild = await GuildConfig.get_guild(message.guild.id)
		return guild.prefix or DEFAULT_PREFIX

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

			raise exc

			try:
				raise exc
			except Exception:
				log.exception(f'Unhandled command error:')
				raise exc

		if isinstance(exc, commands.CommandInvokeError):
			exc = exc.original
			await log_and_raise()

		if isinstance(exc, (commands.ConversionError, commands.UserInputError)):
			prefix = await self.prefix_resolver(self, ctx.message)
			e.title = str(exc)
			e.description = f'Usage: `{prefix}{ctx.command.qualified_name} {ctx.command.signature}`'

		elif isinstance(exc, commands.DisabledCommand):
			e.description = 'Sorry, command has been disabled by owner. Try again later!'

		elif isinstance(exc, commands.CommandOnCooldown):
			e.title = 'You are on cooldown.'
			e.description = f'Try again in {pretty_seconds(exc.retry_after)}'

		elif isinstance(exc, commands.BotMissingPermissions):
			e.title = 'Bot is missing permissions to run command:'
			e.description = ', '.join(perm.replace('_', ' ').title() for perm in exc.missing_perms)

		elif isinstance(exc, (commands.CheckFailure, commands.CommandNotFound)):
			return # *specifically* do nothing on these

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
