import discord
import asyncpg
import aiohttp
import logging
import traceback
import logging.handlers
import sys
import os
import json

from discord.ext import commands
from pprint import saferepr
from datetime import datetime

from config import *
from cogs.help import PaginatedHelpCommand, EditedMinimalHelpCommand
from utils.time import pretty_seconds
from utils.string_helpers import repr_ctx
from utils.configtable import ConfigTable, GuildConfigRecord
from utils.checks import set_bot

EXTENSIONS = (
	'cogs.general',
	'cogs.images',
	'cogs.configuration',
	'cogs.mod',
	'cogs.whois',
	'cogs.tags',
	'cogs.stars',
	'cogs.meta',
	'cogs.trivia',
	'cogs.remind',
	'cogs.hl',
	'cogs.welcome',
	'cogs.roles',
	'cogs.ahk.ahk',
	'cogs.security',
	'cogs.ahk.logger',
	'cogs.ahk.security',
	'cogs.dwitter',
	'cogs.owner',
)

self_deleted = list()


class AceBot(commands.Bot):
	support_link = 'https://discord.gg/X7abzRe'

	def __init__(self):
		set_bot(self)

		log.info('Starting...')

		super().__init__(
			command_prefix=self.prefix_resolver,
			owner_id=OWNER_ID,
			description=DESCRIPTION,
			help_command=EditedMinimalHelpCommand(),
			max_messages=20000,
		)

		self.aiohttp = None
		self.db = None
		self.config = None
		self.self_deleted = self_deleted
		self.startup_time = datetime.utcnow()

		# do blacklist check before all commands
		self.add_check(self.blacklist, call_once=True)

	async def on_connect(self):
		'''Called on connection with the Discord gateway.'''

		log.info('Connected to Discord...')
		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_ready(self):
		'''Called when discord.py has finished connecting to the gateway.'''

		if self.db is None:
			log.info('Creating database connection...')

			self.config = ConfigTable(self, table='config', primary='guild_id', record_class=GuildConfigRecord)

			self.static_help_command = self.help_command
			command_impl = self.help_command._command_impl
			self.help_command = PaginatedHelpCommand()
			self.static_help_command._command_impl = command_impl

			log.info('Initializing aiohttp')
			self.aiohttp = aiohttp.ClientSession(
				loop=self.loop,
				timeout=aiohttp.ClientTimeout(total=5)
			)

			self.db = await asyncpg.create_pool(DB_BIND)

			for extension in filter(lambda extension: os.path.isfile(extension.replace('.', '/') + '.py'), EXTENSIONS):
				log.info(f'loading {extension}')
				self.load_extension(extension)

			self.loop.create_task(self.update_dbl())

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
			perms = 268823632
		return f'https://discordapp.com/oauth2/authorize?&client_id={self.user.id}&scope=bot&permissions={perms}'

	async def prefix_resolver(self, bot, message):
		if message.guild is None:
			return DEFAULT_PREFIX

		gc = await self.config.get_entry(message.guild.id)
		return gc.prefix or DEFAULT_PREFIX

	async def blacklist(self, ctx):
		if ctx.author.bot:
			return False

		if ctx.guild is None:
			return False

		if not ctx.guild.me.permissions_in(ctx.channel).send_messages:
			return False

		return True

	async def on_command_error(self, ctx, exc):
		e = discord.Embed()

		async def send_error():
			try:
				if ctx.guild.me.permissions_in(ctx.channel).embed_links:
					await ctx.send(embed=e)
				else:
					content = ''
					if isinstance(e.title, str):
						content += e.title
					elif isinstance(e.author.name, str):
						content += e.author.name

					if isinstance(e.description, str) and len(e.description):
						content += '\n' + e.description

					await ctx.send(content)
			except discord.HTTPException:
				pass

		async def log_and_raise():
			nonlocal send_error

			e.set_author(name='An error occured.', icon_url=self.user.avatar_url)
			e.description = (
				'The error has been saved and will hopefully be fixed. Thanks for using the bot!'
			)

			await send_error()

			timestamp = str(datetime.utcnow()).split('.')[0].replace(' ', '_').replace(':', '')
			filename = str(ctx.message.id) + '_' + timestamp + '.error'

			try:
				raise exc
			except Exception:
				tb = traceback.format_exc()

			content = (
				'{}\n\nMESSAGE CONTENT:\n{}\n\nCOMMAND: {}\nARGS: {}\nKWARGS: {}\n\nTRACEBACK:\n{}'
			).format(
				repr_ctx(ctx), ctx.message.content, ctx.command.qualified_name,
				saferepr(ctx.args[2:]), saferepr(ctx.kwargs), tb
			)

			with open('error/{}'.format(filename), 'w', encoding='utf-8-sig') as f:
				f.write(content)

			raise exc

		if isinstance(exc, commands.CommandInvokeError):
			if isinstance(exc.original, discord.Forbidden):
				return  # ignore forbidden errors
			await log_and_raise()

		elif isinstance(exc, (commands.ConversionError, commands.UserInputError)):
			e.title = str(exc)
			e.description = f'Usage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`'

		elif isinstance(exc, commands.DisabledCommand):
			e.description = 'Sorry, command has been disabled by owner. Try again later!'

		elif isinstance(exc, commands.CommandOnCooldown):
			e.title = 'You are on cooldown.'
			e.description = f'Try again in {pretty_seconds(exc.retry_after)}.'

		elif isinstance(exc, commands.BotMissingPermissions):
			e.description = str(exc)

		elif isinstance(exc, (commands.CheckFailure, commands.CommandNotFound)):
			return # *specifically* do nothing on these

		elif isinstance(exc, commands.CommandError):
			e.description = str(exc)

		elif isinstance(exc, discord.DiscordException):
			await log_and_raise()

		await send_error()

	async def on_guild_join(self, guild):
		log.info('Join guild {0.name} {0.id}'.format(guild))
		await self.update_dbl()

	async def on_guild_remove(self, guild):
		log.info('Left guild {0.name} {0.id}'.format(guild))
		await self.update_dbl()

	async def update_dbl(self):
		'''Sends an update on guild count to dbl.'''

		url = 'https://discordbots.org/api/bots/{}/stats'.format(self.user.id)

		server_count = len(self.guilds)
		data = dict(server_count=server_count)

		headers = {
			'Content-Type': 'application/json',
			'Authorization': DBL_KEY
		}

		async with self.aiohttp.post(url, data=json.dumps(data), headers=headers) as resp:
			if resp.status == 200:
				log.info('Updated DBL with server count {}'.format(server_count))
			else:
				log.info('Failed updating DBL: {} - {}'.format(resp.reason, await resp.text()))

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
	for path in ('data', 'logs', 'error', 'feedback'):
		if not os.path.exists(path):
			os.makedirs(path)

	# init first log file
	if not os.path.isfile('logs/log.log'):
		open('logs/log.log', 'w+')

	# set logging levels for discord and gino lib
	logging.getLogger('discord').setLevel(logging.DEBUG)
	logging.getLogger('asyncpg').setLevel(logging.DEBUG)

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
