import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime
from pprint import saferepr

import aiohttp
import asyncpg
import discord
from discord.ext import commands

from cogs.help import PaginatedHelpCommand, EditedMinimalHelpCommand
from config import *
from utils.configtable import ConfigTable, ConfigTableRecord
from utils.context import AceContext
from utils.fakemember import FakeMember
from utils.time import pretty_seconds

EXTENSIONS = (
	'cogs.general',
	'cogs.images',
	'cogs.configuration',
	'cogs.tags',
	'cogs.stars',
	'cogs.meta',
	'cogs.mod',
	'cogs.games',
	'cogs.remind',
	'cogs.feeds',
	'cogs.hl',
	'cogs.welcome',
	'cogs.roles',
	'cogs.whois',
	'cogs.ahk.ahk',
	'cogs.security',
	'cogs.ahk.logger',
	'cogs.ahk.security',
	'cogs.ahk.challenges',
	'cogs.dwitter',
	'cogs.linus',
	'cogs.owner'
)

self_deleted = list()


class GuildConfigRecord(ConfigTableRecord):
	@property
	def mod_role(self):
		if self.mod_role_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)

		if guild is None:
			return None

		return guild.get_role(self.mod_role_id)

	@property
	def mute_role(self):
		if self.mute_role_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)

		if guild is None:
			return None

		return guild.get_role(self.mute_role_id)

	@property
	def log_channel(self):
		if self.log_channel_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)
		if guild is None:
			return None

		return guild.get_channel(self.log_channel_id)


class AceBot(commands.Bot):
	support_link = 'https://discord.gg/X7abzRe'

	def __init__(self):
		log.info('Starting...')

		super().__init__(
			command_prefix=self.prefix_resolver,
			owner_id=OWNER_ID,
			description=DESCRIPTION,
			help_command=EditedMinimalHelpCommand(),
			max_messages=20000,
			activity=BOT_ACTIVITY,
		)

		self.aiohttp = None
		self.db = None
		self.config = None
		self.self_deleted = self_deleted
		self.startup_time = datetime.utcnow()

	async def on_connect(self):
		'''Called on connection with the Discord gateway.'''

		log.info('Connected to Discord...')

	async def on_ready(self):
		'''Called when discord.py has finished connecting to the gateway.'''

		if self.db is None:
			log.info('Creating database connection...')

			self._mention_startswith = '<@!{}>'.format(self.user.id)

			self.config = ConfigTable(self, table='config', primary='guild_id', record_class=GuildConfigRecord)

			self.static_help_command = self.help_command
			command_impl = self.help_command._command_impl
			self.help_command = PaginatedHelpCommand()
			self.static_help_command._command_impl = command_impl

			# rebind help command to call ctx.send_help instead
			self.remove_command('help')
			self.add_command(commands.Command(self._help, name='help'))

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

	async def _help(self, ctx, *, command=None):
		await ctx.send_help(command)

	async def on_resumed(self):
		log.info('Resumed...')

		# re-set presence on connection resumed
		await self.change_presence()
		await self.change_presence(activity=BOT_ACTIVITY)

	async def on_guild_unavailable(self, guild):
		log.info(f'Guild "{guild.name}" unavailable')

	async def on_command_completion(self, ctx):
		await ctx.db.execute(
			'INSERT INTO log (guild_id, channel_id, user_id, timestamp, command) VALUES ($1, $2, $3, $4, $5)',
			ctx.guild.id, ctx.channel.id, ctx.author.id, datetime.utcnow(), ctx.command.qualified_name
		)

	async def on_message(self, message):
		if message.guild is None or message.author.bot:
			return

		if self.db is None or not self.db._initialized:
			return

		await self.process_commands(message)

	async def process_commands(self, message):
		ctx = await self.get_context(message, cls=AceContext)

		# if message starts with our mention, trigger a help invoke
		if message.content.startswith(self._mention_startswith):
			ctx.bot = self
			ctx.prefix = await self.prefix_resolver(self, message)
			command = message.content[message.content.find('>') + 1:].strip()
			await ctx.send_help(command or None)
			return

		if ctx.command is None:
			return

		perms = ctx.perms
		if not perms.send_messages or not perms.read_message_history:
			return

		await self.invoke(ctx)

	@property
	def invite_link(self):
		return 'https://discordapp.com/oauth2/authorize?&client_id={0}&scope=bot&permissions={1}'.format(
			self.user.id, 268823632
		)

	async def prefix_resolver(self, bot, message):
		if message.guild is None:
			return DEFAULT_PREFIX

		gc = await self.config.get_entry(message.guild.id)
		return gc.prefix or DEFAULT_PREFIX

	async def on_command_error(self, ctx, exc):
		e = discord.Embed(color=0x36393E)

		async def send_error():
			try:
				if ctx.perms.embed_links:
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

			e.set_author(name='Oops!', icon_url=self.user.avatar_url)
			e.description = (
				'An exception occured while processing the command.\nMy developer has been notified and the issue will '
				'hopefully be fixed soon!\n\n'
				'You can join the support server [here]({0}).'
			).format(
				self.support_link
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
				ctx.stamp, ctx.message.content, ctx.command.qualified_name,
				saferepr(ctx.args[2:]), saferepr(ctx.kwargs), tb
			)

			with open('error/{}'.format(filename), 'w', encoding='utf-8-sig') as f:
				f.write(content)

			raise exc

		if isinstance(exc, commands.CommandInvokeError):
			if isinstance(exc.original, discord.Forbidden):
				return  # ignore forbidden errors
			await log_and_raise()

		elif isinstance(exc, commands.ConversionError):
			await log_and_raise()

		elif isinstance(exc, commands.UserInputError):
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
			return  # *specifically* do nothing on these

		elif isinstance(exc, commands.CommandError):
			e.description = str(exc)

		elif isinstance(exc, discord.DiscordException):
			await log_and_raise()

		await send_error()

	async def on_guild_join(self, guild):
		log.info('Join guild {0.name} ({0.id})'.format(guild))
		await self.update_dbl()

	async def on_guild_remove(self, guild):
		log.info('Left guild {0.name} ({0.id})'.format(guild))
		await self.update_dbl()

	async def update_dbl(self):
		'''Sends an update on guild count to dbl.'''

		if DBL_KEY is None:
			return

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

	@commands.Cog.listener()
	async def on_log(self, member_or_message, action=None, reason=None, severity=0):
		if isinstance(member_or_message, discord.Message):
			message = member_or_message
			member = message.author
		elif isinstance(member_or_message, (discord.Member, FakeMember)):
			message = None
			member = member_or_message
		else:
			raise TypeError('Unsupported type: {}'.format(type(member_or_message)))

		guild = member.guild

		conf = await self.config.get_entry(guild.id)

		log_channel = conf.log_channel

		if log_channel is None:
			return

		desc = 'NAME: {0.display_name}\nMENTION: {0.mention}'.format(member)

		color = [discord.Embed().color, 0xFF8C00, 0xFF2000][severity]

		e = discord.Embed(
			title=action or 'INFO',
			description=desc,
			color=color,
			timestamp=datetime.utcnow()
		)

		if reason is not None:
			e.add_field(name='Reason', value=reason)

		if hasattr(member, 'avatar_url'):
			e.set_thumbnail(url=member.avatar_url)

		e.set_footer(text='{} - ID: {}'.format(['LOW', 'MEDIUM', 'HIGH'][severity], member.id))

		if message is not None:
			e.add_field(name='Context', value='[Click here]({})'.format(message.jump_url), inline=False)

		await log_channel.send(embed=e)


# TODO: rely on logging to fetch self-deleted messages instead of monkey-patching?
async def patched_delete(self, *, delay=None):
	self_deleted.insert(0, self.id)

	if len(self_deleted) > 100:
		self_deleted.pop()

	await self.real_delete(delay=delay)


discord.Message.real_delete = discord.Message.delete
discord.Message.delete = patched_delete


async def patched_execute(self, query, args, limit, timeout, return_status=False):
	log.debug(query)
	return await self._real_execute(query, args, limit, timeout, return_status)


asyncpg.Connection._real_execute = asyncpg.Connection._execute
asyncpg.Connection._execute = patched_execute


# monkey-patched Embed class to force embed color
class Embed(discord.Embed):
	def __init__(self, color=discord.Color.blue(), **attrs):
		attrs['color'] = color
		super().__init__(**attrs)


discord.Embed = Embed


def init_folders():
	# create additional folders
	for path in ('data', 'logs', 'error', 'feedback'):
		if not os.path.exists(path):
			os.makedirs(path)


def init_logging():
	global log

	# init first log file
	if not os.path.isfile('logs/log.log'):
		open('logs/log.log', 'w+')

	# set logging levels for discord and asyncpg
	logging.getLogger('discord').setLevel(logging.INFO)
	logging.getLogger('websockets').setLevel(logging.INFO)
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


if __name__ == '__main__':
	# inits
	init_folders()
	init_logging()

	AceBot().run(BOT_TOKEN)
