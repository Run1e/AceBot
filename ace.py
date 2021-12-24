import asyncio
import logging.handlers
import os
from datetime import datetime

import aiohttp
import asyncpg
from disnake.ext import commands

from config import *
from utils.configtable import ConfigTable
from utils.context import AceContext
from utils.guildconfigrecord import GuildConfigRecord
from utils.help import PaginatedHelpCommand
from utils.string import po

EXTENSIONS = (
	'cogs.test',
	'cogs.backend.error_handler',
	'cogs.backend.logger',
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

	aiohttp: aiohttp.ClientSession
	db: asyncpg.pool
	config: ConfigTable
	startup_time: datetime

	def __init__(self, **kwargs):
		super().__init__(
			command_prefix=self.prefix_resolver,
			owner_id=OWNER_ID,
			description=DESCRIPTION,
			help_command=PaginatedHelpCommand(),
			max_messages=20000,
			activity=disnake.Game('Booting up...'),
			status=disnake.Status.do_not_disturb,
			**kwargs
		)

		# created in login
		self.db = None

		self.config = ConfigTable(self, table='config', primary='guild_id', record_class=GuildConfigRecord)

		self.startup_time = datetime.utcnow()

		self.log = logging.getLogger('acebot')

		aiohttp_log = logging.getLogger('http')

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

	async def on_connect(self):
		self.log.info('Connected to gateway!')

	async def on_resumed(self):
		self.log.info('Reconnected to gateway!')

		# re-set presence on connection resumed
		await self.change_presence()
		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_ready(self):
		await self.change_presence(activity=BOT_ACTIVITY, status=disnake.Status.online)
		self.log.info('Ready! %s', po(self.user))

	async def on_message(self, message):
		# ignore DMs and bot accounts
		if message.guild is None or message.author.bot:
			return

		# don't process commands before bot is ready
		if not self.is_ready():
			# rather than wait for the bot to be ready, we return to avoid users
			# who send their commands multiple times from being processed.
			return

		await self.process_commands(message)

	async def process_commands(self, message: disnake.Message):
		if message.author.bot:
			return

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

	def load_extensions(self):
		reloaded = list()

		for name in EXTENSIONS:
			file_name = name.replace('.', '/') + '.py'

			if os.path.isfile(file_name):
				mtime = os.stat(file_name).st_mtime_ns

				if mtime > self.modified_times.get(name, 0):
					if name in self.extensions.keys():
						meth = self.reload_extension
					else:
						meth = self.load_extension

					self.log.debug('Loading %s', name)

					meth(name)
					self.modified_times[name] = mtime

					reloaded.append(name)

		return reloaded

	@property
	def invite_link(self):
		return disnake.utils.oauth_url(
			self.user.id,
			permissions=disnake.Permissions(1374658358486),
			scopes=['bot', 'applications.commands'],
		)

	async def login(self, token: str) -> None:
		self.log.info('Creating postgres pool')
		self.db = await asyncpg.create_pool(DB_BIND)
		self.log.info('Loading extensions')
		self.load_extensions()
		self.log.info('Logging in to discord')
		return await super().login(token)


if __name__ == '__main__':
	import sys

	print('The entry point has moved, use main.py to run the bot now.')
	sys.exit(1)
