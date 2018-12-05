import discord, aiohttp, logging, dbl, asyncio, traceback
from discord.ext import commands
from math import floor
from datetime import datetime
from sqlalchemy import and_

from utils.database import setup_db, GuildModule, IgnoredUser
from utils.setup_logger import config_logger
from config import *

log = logging.getLogger(__name__)
log = config_logger(log)

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
	'cogs.configuration',
	'cogs.meta',
	'cogs.verify',
	'cogs.mod',
	'cogs.hl',
	'cogs.welcome',
	'cogs.roles',
	'cogs.guild.ahk',
	'cogs.owner',
	'cogs.help',
)


class AceBot(commands.Bot):
	_toggleable = []
	_default_modules = ['tags', 'stats']
	
	_support_link = 'https://discord.gg/X7abzRe'
	
	def __init__(self):
		log.info('Launching')
		
		super().__init__(
			command_prefix=command_prefix,
			owner_id=owner_id,
			description=description
		)
		
		# do blacklist check before all commands
		self.add_check(self.blacklist)
	
	# run on successful connection
	async def on_ready(self):
		if not hasattr(self, 'startup_time'):
			self.startup_time = datetime.now()
			
			# add dblpy updater
			self.dblpy = dbl.Client(self, dbl_key)
			await self.update_dbl()
		
		log.info('Connected, starting setup')
		
		log.info('Connecting to database')
		self.db = await setup_db(db_bind, loop=self.loop)
		
		log.info('Initializing aiohttp')
		self.aiohttp = aiohttp.ClientSession(
			loop=self.loop,
			timeout=aiohttp.ClientTimeout(
				total=4
			)
		)
		
		self.remove_command('help')
		
		# load extensions
		for extension in extensions:
			log.info(f'Loading extension: {extension}')
			self.load_extension(extension)
		
		await self.update_status()
		
		log.info('Finished!')
	
	async def update_dbl(self):
		try:
			await self.dblpy.post_server_count()
		except Exception as exc:
			log.error(f'Failed updating DBL: {str(exc)}')
	
	async def uses_module(self, ctx, mod):
		'''Checks if any context should allow a module to run.'''
		
		return await GuildModule.query.where(
			and_(
				GuildModule.guild_id == ctx.guild.id,
				GuildModule.module == mod.lower()
			)
		).gino.scalar()
	
	async def blacklist(self, ctx):
		'''Returns False if user is disallowed, otherwise True'''
		
		# ignore other bots
		if ctx.author.bot:
			return False
		
		# ignore DMs
		if ctx.guild is None:
			return False
		
		# ignore ignored users
		if await IgnoredUser.query.where(IgnoredUser.user_id == ctx.author.id).gino.scalar():
			return False
		
		# make sure we're not in a verification channel
		if ctx.channel.name == f'welcome-{ctx.author.id}' and await self.uses_module(ctx, 'verify'):
			return False
		
		return True
	
	async def on_guild_join(self, guild):
		for module in self._default_modules:
			await GuildModule.create(
				guild_id=guild.id,
				module=module
			)
		
		await self.update_dbl()
		await self.log(f'Joined guild {guild.name} ({guild.id})')
	
	async def on_guild_remove(self, guild):
		await self.update_dbl()
		await self.log(f'Left guild {guild.name} ({guild.id})')
	
	async def update_status(self, *args, **kwargs):
		await self.change_presence(activity=discord.Game(name='.help'))
		return
		
		users = 0
		for guild in filter(lambda guild: guild.id != 264445053596991498, self.guilds):
			users += len(guild.members)
		
		await self.change_presence(activity=discord.Game(name=f'.help | {users} users'))
	
	async def on_command_error(self, ctx, exc):
		if hasattr(exc, 'original'):
			try:
				raise exc.original
			except Exception:
				chan = self.get_channel(error_channel)
				await chan.send(embed=self.embed_from_ctx(ctx))
				await chan.send(f'```{traceback.format_exc()}```')
			raise exc.original
		
		title = str(exc)
		extra = None
		
		if isinstance(exc, commands.UserInputError):
			extra = f'Usage: `{self.command_prefix}{ctx.command.signature}`'
		elif isinstance(exc, commands.CommandOnCooldown):
			title, extra = 'You are on cooldown.', f'Try again in {floor(exc.retry_after)} seconds.'
		elif isinstance(exc, commands.BotMissingPermissions):
			title = 'Bot is missing permissions to run command.'
			extra = '\n'.join(perm.replace('_', ' ').title() for perm in exc.missing_perms)
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
		
		await ctx.send(embed=discord.Embed(title=title, description=extra))
	
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
		
		e.timestamp = datetime.now()
		
		return e


# monkey-patched Embed class to force embed color
class Embed(discord.Embed):
	def __init__(self, color=0x2E4D83, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)


discord.Embed = Embed

if __name__ == '__main__':
	AceBot().run(token)
