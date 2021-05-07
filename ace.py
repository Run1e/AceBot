import asyncio
import json
import logging.handlers
import os
import sys
import traceback
from datetime import datetime

import aiohttp
import asyncpg
from discord.ext import commands

from config import *
from utils.colorstreamhandler import ColorStreamHandler
from utils.commanderrorlogic import CommandErrorLogic
from utils.configtable import ConfigTable
from utils.context import AceContext
from utils.guildconfigrecord import GuildConfigRecord
from utils.help import EditedMinimalHelpCommand, PaginatedHelpCommand
from utils.string import po
from utils.time import pretty_seconds

EXTENSIONS = (
	'cogs.fun',
	'cogs.configuration',
	'cogs.tags',
	'cogs.stars',
	'cogs.meta',
	'cogs.mod',
	'cogs.games',
	'cogs.remind',
	'cogs.welcome',
	'cogs.roles',
	'cogs.whois',
	'cogs.hl',
	'cogs.ahk.ahk',
	'cogs.ahk.help',
	'cogs.ahk.internal.logger',
	'cogs.ahk.internal.security',
	'cogs.dwitter',
	'cogs.owner',
)


class AceBot(commands.Bot):
	support_link = 'https://discord.gg/X7abzRe'

	ready: asyncio.Event
	aiohttp: aiohttp.ClientSession
	db: asyncpg.pool
	config: ConfigTable
	startup_time: datetime

	def __init__(self, db, **kwargs):
		super().__init__(
			command_prefix=self.prefix_resolver,
			owner_id=OWNER_ID,
			description=DESCRIPTION,
			help_command=EditedMinimalHelpCommand(),
			max_messages=20000,
			activity=BOT_ACTIVITY,
			**kwargs
		)

		self.db = db
		self.config = ConfigTable(self, table='config', primary='guild_id', record_class=GuildConfigRecord)

		self.ready = asyncio.Event()
		self.startup_time = datetime.utcnow()

		aiohttp_log = logging.getLogger('aiotrace')

		async def on_request_end(session, ctx, end):
			resp = end.response
			aiohttp_log.info(
				'[%s %s] %s %s (%s)',
				str(resp.status), resp.reason, end.method.upper(), end.url, resp.content_type
			)

		trace_config = aiohttp.TraceConfig()
		trace_config.on_request_end.append(on_request_end)

		self.aiohttp = aiohttp.ClientSession(
			loop=self.loop,
			timeout=aiohttp.ClientTimeout(total=5),
			trace_configs=[trace_config],
		)

		self.modified_times = dict()

		# help command. this is messy but it has to be because the lib doesn't really like you having
		# two different help commands. maybe I will see if I can clean this up in the future
		self.static_help_command = self.help_command
		command_impl = self.help_command._command_impl
		self.help_command = PaginatedHelpCommand()
		self.static_help_command._command_impl = command_impl

		self.remove_command('help')
		self.add_command(commands.Command(self._help, name='help'))

	async def _help(self, ctx, *, command=None):
		await ctx.send_help(command)

	async def on_connect(self):
		log.info('Connected...')

	async def on_resumed(self):
		log.info('Resumed...')

		# re-set presence on connection resumed
		await self.change_presence()
		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_ready(self):
		if not self.ready.is_set():
			self.load_extensions()

			self.loop.create_task(self.update_dbl())

			self.ready.set()
			log.info('Ready! %s', po(self.user))

	async def on_message(self, message):
		if message.guild is None or message.author.bot:
			return

		if not self.ready.is_set():
			await self.ready.wait()

		await self.process_commands(message)

	async def process_commands(self, message: discord.Message):
		ctx: AceContext = await self.get_context(message, cls=AceContext)

		# if messages starts with a bot mention...
		if message.content.startswith((self.user.mention, '<@!%s>' % self.user.id)):
			# set the bot prefix and invoke the help command
			prefixes = await self.prefix_resolver(self, message)
			ctx.prefix = prefixes[-1]
			command = message.content[message.content.find('>') + 1:].strip()
			await ctx.send_help(command or None)
			return

		if ctx.command is None:
			return

		perms = ctx.perms
		if not perms.send_messages or not perms.read_message_history:
			return

		await self.invoke(ctx)

	async def prefix_resolver(self, bot, message):
		if message.guild is None:
			return DEFAULT_PREFIX

		gc = await self.config.get_entry(message.guild.id)
		return gc.prefix or DEFAULT_PREFIX

	def load_extensions(self, reload: bool=False):
		"""Reload bot Extensions. 

		If `reload` is False, then cogs are unloaded and loaded.
		If `reload` is True, then cogs are reloaded using `reload_extension()`

		"""

		reloaded = list()
		errored = list()

		for name in EXTENSIONS:
			file_name = name.replace('.', '/') + '.py'

			if os.path.isfile(file_name):
				mtime = os.stat(file_name).st_mtime_ns

				if mtime > self.modified_times.get(name, 0):

					if name in self.extensions.keys() and not reload:
						self.unload_extension(name)

					try:
						log.debug('Loading %s', name)

						if reload:

							try:
								self.reload_extension(name)
							except commands.ExtensionNotLoaded:
								self.load_extension(name)
						else:
							self.load_extension(name)
						self.modified_times[name] = mtime

						reloaded.append(name)

					except Exception as e:

						if not DEV_MODE:
							raise e

						log.error(f'Failed to load extension: {name}')
						log.error(e)
						errored.append((name, e.args[0].lstrip(f"Extension '{name}' raised an error:")))
						print("".join(traceback.format_exception(*sys.exc_info())).strip())

		return reloaded, errored

	async def on_command(self, ctx):
		spl = ctx.message.content.split('\n')
		log.info('%s in %s: %s', po(ctx.author), po(ctx.guild), spl[0] + (' ...' if len(spl) > 1 else ''))

	async def on_command_completion(self, ctx: AceContext):
		await ctx.db.execute(
			'INSERT INTO log (guild_id, channel_id, user_id, timestamp, command) VALUES ($1, $2, $3, $4, $5)',
			ctx.guild.id, ctx.channel.id, ctx.author.id, datetime.utcnow(), ctx.command.qualified_name
		)

	async def on_command_error(self, ctx, exc):
		async with CommandErrorLogic(ctx, exc) as handler:
			if isinstance(exc, commands.CommandInvokeError):
				if isinstance(exc.original, discord.HTTPException):
					log.debug('Command failed with %s', str(exc.original))
					return
				handler.oops()

			elif isinstance(exc, commands.ConversionError):
				handler.oops()

			elif isinstance(exc, commands.UserInputError):
				handler.set(
					title=str(exc),
					description='Usage: `{0.prefix}{1.qualified_name} {1.signature}`'.format(ctx, ctx.command)
				)

			elif isinstance(exc, commands.DisabledCommand):
				handler.set(description='Sorry, command has been disabled by owner. Try again later!')

			elif isinstance(exc, commands.CommandOnCooldown):
				handler.set(
					title='You are on cooldown.',
					description='Try again in {0}.'.format(pretty_seconds(exc.retry_after))
				)

			elif isinstance(exc, commands.BotMissingPermissions):
				handler.set(description=str(exc))

			elif isinstance(exc, (commands.CheckFailure, commands.CommandNotFound)):
				return

			elif isinstance(exc, commands.CommandError):
				handler.set(description=str(exc))

			elif isinstance(exc, discord.DiscordException):
				handler.oops()

	async def on_guild_join(self, guild):
		log.info('Join guild %s', po(guild))
		await self.update_dbl()

	async def on_guild_remove(self, guild):
		log.info('Left guild %s', po(guild))
		await self.update_dbl()

	async def on_guild_unavailable(self, guild):
		pass #log.info('Unavailable guild %s', str(guild))

	@property
	def invite_link(self):
		return 'https://discordapp.com/oauth2/authorize?&client_id={0}&scope=bot&permissions={1}'.format(
			self.user.id, 268823632
		)

	async def update_dbl(self):
		'''Sends an update on guild count to dbl.'''

		if DBL_KEY is None:
			return

		if not self.is_ready():
			await self.wait_until_ready()

		url = 'https://discordbots.org/api/bots/{}/stats'.format(self.user.id)

		server_count = len(self.guilds)
		data = dict(server_count=server_count)

		headers = {
			'Content-Type': 'application/json',
			'Authorization': DBL_KEY
		}

		async with self.aiohttp.post(url, data=json.dumps(data), headers=headers) as resp:
			if resp.status == 200:
				log.info('Updated DBL with server count %s', server_count)
			else:
				log.info('Failed updating DBL: %s - %s', resp.reason, await resp.text())


def setup_logger():
	# init first log file
	if not os.path.isfile('logs/log.log'):
		open('logs/log.log', 'w+')

	# set logging levels for various libs
	logging.getLogger('discord').setLevel(logging.INFO)
	logging.getLogger('websockets').setLevel(logging.INFO)
	logging.getLogger('asyncpg').setLevel(logging.INFO)
	logging.getLogger('asyncio').setLevel(logging.INFO)

	# we want out logging formatted like this everywhere
	fmt = logging.Formatter('{asctime} [{levelname}] {name}: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{')

	stream = ColorStreamHandler(sys.stdout)
	stream.setFormatter(fmt)
	stream.setLevel(logging.DEBUG)

	file = logging.handlers.TimedRotatingFileHandler('logs/log.log', when='midnight', encoding='utf-8-sig')
	file.setFormatter(fmt)
	file.setLevel(logging.INFO)

	# get the __main__ logger and add handlers
	root = logging.getLogger()
	root.setLevel(LOG_LEVEL)
	root.addHandler(stream)
	root.addHandler(file)

	return logging.getLogger(__name__)


async def setup():
	# create folders
	for path in ('data', 'logs', 'error', 'feedback', 'ahk_eval'):
		if not os.path.exists(path):
			log.info('Creating folder: %s', path)
			os.makedirs(path)

	# misc. monkey-patching
	class Embed(discord.Embed):
		def __init__(self, color=discord.Color.blue(), **attrs):
			attrs['color'] = color
			super().__init__(**attrs)

	discord.Embed = Embed

	def patched_execute(old):
		async def new(self, query, args, limit, timeout, return_status=False):
			log.debug(query)
			return await old(self, query, args, limit, timeout, return_status)

		return new

	asyncpg.Connection._execute = patched_execute(asyncpg.Connection._execute)

	# connect to db
	log.info('Creating postgres pool')
	db = await asyncpg.create_pool(DB_BIND)

	# create allowed mentions
	allowed_mentions = discord.AllowedMentions(everyone=False, users=True, roles=False, replied_user=True)

	# init bot
	log.info('Initializing bot')
	bot = AceBot(db=db, loop=loop, intents=BOT_INTENTS, allowed_mentions=allowed_mentions)

	# start it
	log.info('Logging in and starting bot')
	await bot.start(BOT_TOKEN)


if __name__ == '__main__':
	log = setup_logger()
	loop = asyncio.get_event_loop()

	loop.run_until_complete(setup())
