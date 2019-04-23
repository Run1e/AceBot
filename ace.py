import discord, aiohttp, dbl, traceback, io, logging, logging.handlers, sys, os
from discord.ext import commands
from datetime import datetime

from cogs.guild.ahk.ids import AHK_GUILD_ID, MEMBER_ROLE_ID
from utils.time import pretty_seconds
from utils.database import db, setup_db
from config import *

description = '''
A.C.E. - Autonomous Command Executor

Written and maintained by RUNIE 🔥#9646
Contributions: Vinter Borge, Cap'n Odin#8812, and GeekDude#2532
'''

extensions = (
	'cogs.general',
	'cogs.configuration',
	'cogs.mod',
	'cogs.images',
	'cogs.tags',
	'cogs.stats',
	'cogs.starboard',
	'cogs.reminder',
	'cogs.meta',
	'cogs.welcome',
	'cogs.hl',
	'cogs.coins',
	'cogs.quiz',
	'cogs.guild.ahk.ahk',
	'cogs.guild.dwitter',
	'cogs.owner',
	'cogs.help'
)

extensions_if_exist = (
	'cogs.guild.ahk.log',
	'cogs.guild.ahk.security',
	'cogs.guild.ahk.antimention',
)


class AceBot(commands.Bot):
	_module_cache = {}
	_ignored = []
	_toggleable = []

	_support_link = 'https://discord.gg/X7abzRe'

	def __init__(self):
		log.info('Initializing...')

		super().__init__(
			command_prefix=COMMAND_PREFIX,
			owner_id=OWNER_ID,
			description=description
		)

		# do blacklist check before all commands
		self.add_check(self.blacklist, call_once=True)

		# remove the default help command
		self.remove_command('help')

	async def on_connect(self):
		log.info('Connected to Discord...')

	# run on successful connection
	async def on_ready(self):
		if not hasattr(self, 'startup_time'):
			self.startup_time = datetime.utcnow()

			# add dblpy updater
			if DBL_KEY is not None:
				self.dblpy = dbl.Client(self, DBL_KEY)
				await self.update_dbl()

		log.info('Ready! - starting setup')

		log.info('Connecting to database')
		self.db = await setup_db(DB_BIND, loop=self.loop)

		log.info('Initializing aiohttp')
		self.aiohttp = aiohttp.ClientSession(
			loop=self.loop,
			timeout=aiohttp.ClientTimeout(
				total=4
			)
		)

		# load extensions
		for extension in extensions:
			# log.info(f'Loading extension: {extension}')
			self.load_extension(extension)

		for extension in extensions_if_exist:
			if os.path.isfile(extension.replace('.', '/') + '.py'):
				self.load_extension(extension)

		self._ignored = list(*await self.db.all('SELECT user_id FROM ignore'))

		await self.change_presence(activity=discord.Game(name='.help'))

		log.info(f'Invite link: {self.invite_link}')
		log.info(f'Finished! Connected to {len(self.guilds)} guilds.')

	@property
	def invite_link(self, perms=None):
		if perms is None:
			perms = 67497025
		return f'https://discordapp.com/oauth2/authorize?&client_id={self.user.id}&scope=bot&permissions={perms}'

	async def on_resumed(self):
		log.info('Bot resumed...')

	async def on_guild_unavailable(self, guild):
		log.info(f'Guild "{guild.name}" unavailable')

	async def update_dbl(self):
		try:
			await self.dblpy.post_server_count()
		except Exception as exc:
			log.error(f'Failed updating DBL: {str(exc)}')

	def reset_module_cache(self, guild_id=None):
		if guild_id is None:
			self._module_cache.clear()
		else:
			self._module_cache.pop(guild_id, None)

	async def uses_module(self, guild_id, module):
		'''Checks if any context should allow a module to run.'''

		module = module.lower()

		if guild_id not in self._module_cache:
			self._module_cache[guild_id] = {}

		if module not in self._module_cache[guild_id]:
			self._module_cache[guild_id][module] = await self.uses_module_db(guild_id, module)

		return self._module_cache[guild_id][module]

	async def uses_module_db(self, guild_id, module):
		return not not await db.scalar('SELECT id FROM module WHERE guild_id=$1 AND module=$2', guild_id, module.lower())

	async def blacklist(self, ctx):
		'''Returns False if user is disallowed, otherwise True'''

		# ignore other bots, ignore DMs, and ignore ignored users
		if ctx.author.bot or ctx.guild is None or ctx.author.id in self._ignored:
			return False

		# if we're in the ahk guild and the invoker doesn't have the member role, then ONLY
		# allow the command to be run if the command is 'accept' (for #welcome)
		if ctx.guild.id == AHK_GUILD_ID and not any(role.id == MEMBER_ROLE_ID for role in ctx.author.roles):
			return ctx.command is not None and ctx.command.name == 'accept'

		return True

	async def on_guild_join(self, guild):
		await self.update_dbl()

		e = discord.Embed(
			title='Joined guild',
			description=guild.name
		)

		e.set_thumbnail(url=guild.icon_url)
		e.timestamp = datetime.utcnow()

		log.info(f'Joined guild {guild.name} ({guild.id})')
		await self.log(embed=e)

	async def on_guild_remove(self, guild):
		await self.update_dbl()

		e = discord.Embed(
			title='Left guild',
			description=guild.name
		)

		e.set_thumbnail(url=guild.icon_url)
		e.timestamp = datetime.utcnow()

		log.info(f'Left guild {guild.name} ({guild.id})')
		await self.log(embed=e)

	async def update_status(self, *args, **kwargs):
		return
		await self.change_presence(activity=discord.Game(name='.help'))

		users = 0
		for guild in filter(lambda guild: guild.id != 264445053596991498, self.guilds):
			users += len(guild.members)

		await self.change_presence(activity=discord.Game(name=f'.help | {users} users'))

	async def on_command_error(self, ctx, exc):
		if hasattr(exc, 'original'):
			if isinstance(exc.original, discord.Forbidden):
				return

			chan = self.get_channel(ERROR_CHANNEL)

			if chan is not None:
				try:
					raise exc.original
				except Exception:
					tb = traceback.format_exc()

					await chan.send(embed=self.embed_from_ctx(ctx))

					if len(tb) > 1990:
						fp = io.BytesIO(tb.encode('utf-8'))
						await ctx.send('Traceback too large...', file=discord.File(fp, 'results.txt'))
					else:
						await chan.send(f'```{tb}```')

			raise exc.original

		title = str(exc)
		extra = None

		if isinstance(exc, commands.UserInputError):
			extra = f'Usage: `{self.command_prefix}{ctx.command.signature}`'

		elif isinstance(exc, commands.CommandOnCooldown):
			title = 'You are on cooldown.'
			extra = f'Try again in {pretty_seconds(exc.retry_after)}.'

		elif isinstance(exc, commands.BotMissingPermissions):
			title = 'Bot is missing permissions.'
			extra = str(exc)

		elif isinstance(exc, commands.DisabledCommand):
			title = 'This command has been disabled.'
			extra = 'Check back later!'

		elif isinstance(exc, (commands.CommandNotFound, commands.CheckFailure)):
			return  # don't care about these

		elif isinstance(exc, commands.CommandError):
			title = None
			extra = str(exc)

		if extra is None:
			log.debug(f'Unhandled exception of type {type(exc)}: {str(exc)}')
			return

		try:
			if ctx.me.permissions_in(ctx.channel).embed_links:
				await ctx.send(embed=discord.Embed(title=title, description=extra))
			else:
				await ctx.send(f'***{title}***\n\n{extra}')
		except:
			pass

	def embed_from_ctx(self, ctx):
		e = discord.Embed()

		e.set_author(
			name=ctx.guild.name,
			icon_url=ctx.guild.icon_url,
		)

		e.add_field(name='Author', value=ctx.author.name)
		e.add_field(name='Command', value=ctx.command.qualified_name)

		if len(ctx.args) > 2:
			e.add_field(name='args', value=ctx.args[2:])
		if ctx.kwargs:
			e.add_field(name='kwargs', value=ctx.kwargs)

		e.timestamp = datetime.utcnow()

		return e

	async def log(self, content=None, **kwargs):
		chan = self.get_channel(LOG_CHANNEL)
		if chan is not None:
			await chan.send(content=content, **kwargs)


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
	logging.getLogger('discord').setLevel(logging.WARN)
	logging.getLogger('gino').setLevel(logging.WARN)

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
