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
from cogs.ahk.ids import AHK_GUILD_ID, MEMBER_ROLE_ID
from utils.time import pretty_seconds
from utils.guildconfig import GuildConfig

EXTENSIONS = (
	'cogs.general',
	'cogs.images',
	'cogs.configuration',
	'cogs.mod',
	'cogs.whois',
	'cogs.tags',
	'cogs.stars',
	'cogs.meta',
	'cogs.remind',
	'cogs.hl',
	'cogs.welcome',
	'cogs.roles',
	'cogs.ahk.ahk',
	'cogs.security',
	'cogs.ahk.security',
	'cogs.ahk.logger',
	'cogs.owner',
)

self_deleted = list()


class AceBot(commands.Bot):
	_support_link = 'https://discord.gg/X7abzRe'

	def __init__(self):
		log.info('Starting...')

		super().__init__(
			command_prefix=self.prefix_resolver,
			owner_id=OWNER_ID,
			description=DESCRIPTION
		)

		self.aiohttp = None
		self.db = None
		self.self_deleted = self_deleted
		self.startup_time = datetime.utcnow()

		# do blacklist check before all commands
		self.add_check(self.blacklist, call_once=True)

	async def on_connect(self):
		'''Called on connection with the Discord gateway.'''

		log.info('Connected to Discord...')

	async def on_ready(self):
		'''Called when discord.py has finished connecting to the gateway.'''

		if self.db is None:
			log.info('Creating database connection...')

			GuildConfig.set_bot(self)

			self.help_command = Help()

			log.info('Initializing aiohttp')
			self.aiohttp = aiohttp.ClientSession(
				loop=self.loop,
				timeout=aiohttp.ClientTimeout(total=5)
			)

			self.db = await asyncpg.create_pool(DB_BIND)

			for extension in EXTENSIONS:
				log.info(f'loading {extension}')
				self.load_extension(extension)

		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_resumed(self):
		log.info('Resumed...')
		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_guild_unavailable(self, guild):
		log.info(f'Guild "{guild.name}" unavailable')

	async def on_command_completion(self, ctx):
		if ctx.guild is not None:
			await self.db.execute(
				'INSERT INTO log (guild_id, channel_id, user_id, timestamp, command) VALUES ($1, $2, $3, $4, $5)',
				ctx.guild.id, ctx.channel.id, ctx.author.id, datetime.utcnow(), ctx.command.qualified_name
			)

	async def on_message(self, message):
		if self.db is not None and self.db._initialized:
			if message.content.startswith(f'<@{self.user.id}>'):
				ctx = await self.get_context(message)
				ctx.bot = self
				ctx.prefix = await self.prefix_resolver(self, message)
				ctx.command = self.get_command('help')
				await ctx.reinvoke()
			else: # only process commands if db is initialized
				await self.process_commands(message)

	@property
	def invite_link(self, perms=None):
		if perms is None:
			perms = 67497025
		return f'https://discordapp.com/oauth2/authorize?&client_id={self.user.id}&scope=bot&permissions={perms}'

	@staticmethod
	async def prefix_resolver(bot, message):
		gc = await GuildConfig.get_guild(message.guild.id)
		return gc.prefix or DEFAULT_PREFIX

	async def blacklist(self, ctx):
		if ctx.guild is None:
			return False

		if ctx.author.bot:
			return False

		# if we're in the ahk guild and the invoker doesn't have the member role, then ONLY
		# allow the command to be run if the command is 'accept' (for #welcome)
		if ctx.guild.id == AHK_GUILD_ID and not any(role.id == MEMBER_ROLE_ID for role in ctx.author.roles):
			return False

		return True

	async def on_command_error(self, ctx, exc):
		log.info(str(exc))

		e = discord.Embed()

		async def log_and_raise():
			e.description = 'An error occured. The exception has been logged and will hopefully be fixed. Thanks for using the bot!'

			try:
				await ctx.send(embed=e)
			except discord.HTTPException:
				pass

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
			e.description = f'Try again in {pretty_seconds(exc.retry_after)}.'

		elif isinstance(exc, commands.BotMissingPermissions):
			e.title = 'Bot is missing permissions to run command:'
			e.description = ', '.join(perm.replace('_', ' ').title() for perm in exc.missing_perms)

		elif isinstance(exc, (commands.CheckFailure, commands.CommandNotFound)):
			return # *specifically* do nothing on these

		elif isinstance(exc, commands.CommandError):
			e.description = str(exc)

		elif isinstance(exc, discord.DiscordException):
			await log_and_raise()

		try:
			await ctx.send(embed=e)
		except discord.HTTPException:
			pass


# TODO: rely on logging to fetch self-deleted messages instead of monkey-patching?
async def patched_delete(self, *, delay=None):
	self_deleted.insert(0, self.id)

	if len(self_deleted) > 100:
		self_deleted.pop()

	await self.real_delete(delay=delay)

discord.Message.real_delete = discord.Message.delete
discord.Message.delete = patched_delete


# monkey-patched Embed class to force embed color
class Embed(discord.Embed):
	def __init__(self, color=0x2E4D83, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)


discord.Embed = Embed

if __name__ == '__main__':

	# create additional folders
	for path in ('data', 'logs'):
		if not os.path.exists(path):
			os.makedirs(path)

	# init first log file
	if not os.path.isfile('logs/log.log'):
		open('logs/log.log', 'w+')

	# set logging levels for discord and gino lib
	logging.getLogger('discord').setLevel(logging.DEBUG)

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
