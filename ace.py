import discord, aiohttp, dbl, traceback, io, logging, logging.handlers, sys
from discord.ext import commands
from datetime import datetime

from utils.time import pretty_seconds
from utils.database import db, setup_db
from config import *

logging.getLogger('discord').setLevel(logging.WARN)
logging.getLogger('gino').setLevel(logging.WARN)

fmt = logging.Formatter('[{asctime}] [{levelname}] {name}: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{')

stream = logging.StreamHandler(sys.stdout)
stream.setLevel(logging.INFO)
stream.setFormatter(fmt)

file = logging.handlers.TimedRotatingFileHandler('logs/log.log', when='midnight', encoding='utf-8-sig')
file.setLevel(logging.INFO)
file.setFormatter(fmt)

log = logging.getLogger()
log.setLevel(logging.INFO)
log.addHandler(stream)
log.addHandler(file)

description = '''
A.C.E. - Autonomous Command Executor

Written and maintained by RUNIE 🔥#9646
Contributions: Vinter Borge, Cap'n Odin#8812, and GeekDude#2532
'''

extensions = (
	'cogs.general',
	'cogs.images',
	'cogs.tags',
	'cogs.stats',
	'cogs.meta',
	'cogs.starboard',
	'cogs.reminder',
	'cogs.hl',
	'cogs.coins',
	'cogs.welcome',
	'cogs.configuration',
	'cogs.mod',
	#'cogs.warnings',
	'cogs.log',
	'cogs.guild.ahk',
	'cogs.guild.ahk_security',
	'cogs.guild.dwitter',
	'cogs.owner',
	'cogs.help'
)


class AceBot(commands.Bot):
	_toggleable = []

	_support_link = 'https://discord.gg/X7abzRe'

	def __init__(self):
		log.info('Initializing...')

		super().__init__(
			command_prefix=command_prefix,
			owner_id=owner_id,
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
			self.dblpy = dbl.Client(self, dbl_key)
			await self.update_dbl()

		log.info('Ready! - starting setup')

		log.info('Connecting to database')
		self.db = await setup_db(db_bind, loop=self.loop)

		log.info('Initializing aiohttp')
		self.aiohttp = aiohttp.ClientSession(
			loop=self.loop,
			timeout=aiohttp.ClientTimeout(
				total=4
			)
		)

		# load extensions
		for extension in extensions:
			log.info(f'Loading extension: {extension}')
			self.load_extension(extension)

		await self.change_presence(activity=discord.Game(name='.help'))

		log.info('Finished!')

	async def on_resumed(self):
		log.info('Bot resumed...')

	async def on_guild_unavailable(self, guild):
		log.info(f'Guild "{guild.name}" unavailable')

	async def update_dbl(self):
		try:
			await self.dblpy.post_server_count()
		except Exception as exc:
			log.error(f'Failed updating DBL: {str(exc)}')

	async def uses_module(self, guild_id, module):
		'''Checks if any context should allow a module to run.'''

		return await db.scalar('SELECT id FROM module WHERE guild_id=$1 AND module=$2', guild_id, module.lower())

	async def blacklist(self, ctx):
		'''Returns False if user is disallowed, otherwise True'''

		# ignore other bots
		if ctx.author.bot:
			return False

		# ignore DMs
		if ctx.guild is None:
			return False

		# ignore ignored users
		if await db.scalar('SELECT user_id FROM ignore WHERE user_id=$1', ctx.author.id):
			return False


		if ctx.guild.id == 115993023636176902 and ctx.command is not None and ctx.command.name != 'accept' \
		and all(role.id != 509526426198999040 for role in ctx.author.roles):
			return False

		return True

	async def on_guild_join(self, guild):
		await self.update_dbl()

		e = discord.Embed(
			title='Joined guild',
			description=guild.name
		)

		e.set_thumbnail(url=guild.icon_url)
		e.timestamp = datetime.utcnow()

		await self.log(embed=e)

	async def on_guild_remove(self, guild):
		await self.update_dbl()

		e = discord.Embed(
			title='Left guild',
			description=guild.name
		)

		e.set_thumbnail(url=guild.icon_url)
		e.timestamp = datetime.utcnow()

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

			try:
				raise exc.original
			except Exception:
				chan = self.get_channel(error_channel)

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
		await self.get_channel(log_channel).send(content=content, **kwargs)


# monkey-patched Embed class to force embed color
class Embed(discord.Embed):
	def __init__(self, color=0x2E4D83, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)


discord.Embed = Embed

if __name__ == '__main__':
	AceBot().run(token)
