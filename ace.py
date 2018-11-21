import discord, aiohttp, logging
from discord.ext import commands
from math import floor
from datetime import datetime
from sqlalchemy import and_

from utils.database import setup_db, GuildModule, IgnoredUser
from config import *

from utils.setup_logger import config_logger
log = logging.getLogger(__name__)
log = config_logger(log)

extensions = (
	'cogs.commands',
	'cogs.owner',
	'cogs.verify',
	'cogs.moderator',
	'cogs.module',
	'cogs.hl',
	'cogs.tags',
	'cogs.stats',
	'cogs.welcome',
	'cogs.roles',
	'cogs.guild.ahk'
)

class AceBot(commands.Bot):
	
	_toggleable = []
	_default_modules = ['tags', 'stats']
	
	def __init__(self):
		log.info('Launching')
		
		super().__init__(command_prefix=command_prefix, owner_id=owner_id, description=description)
		
		# do blacklist check before all commands
		self.add_check(self.blacklist)
		
		# listeners for when to update status
		self.add_listener(self.update_status, 'on_member_join')
		self.add_listener(self.update_status, 'on_member_remove')
		self.add_listener(self.update_status, 'on_guild_join')
		self.add_listener(self.update_status, 'on_guild_remove')
		
	# run on successful connection
	async def on_ready(self):
		self.startup_time = datetime.now()
		
		log.info('Connected, starting setup')
		
		log.info('Connecting to database')
		self.db = await setup_db(db_bind, loop=self.loop)
		
		log.info('Initializing aiohttp')
		self.aiohttp= aiohttp.ClientSession(
			loop=self.loop,
			timeout=aiohttp.ClientTimeout(
				total=4
			)
		)
		
		# load extensions
		for extension in extensions:
			log.info(f'Loading extension: {extension}')
			self.load_extension(extension)
		
		await self.update_status()
		
		log.info('Finished!')
	
	async def uses_module(self, ctx, mod):
		'''Checks if any context should allow a module to run.'''
		
		return await GuildModule.query.where(
			and_(
				GuildModule.guild_id == ctx.guild.id,
				GuildModule.module == mod.lower()
			)
		).gino.scalar()
		
	async def blacklist(self, ctx):
		'''Returns False if user is blacklisted, otherwise True'''
		
		# ignore other bots
		if ctx.author.bot:
			return False
		
		# only allow invokes from normal text channels
		if not isinstance(ctx.channel, discord.TextChannel):
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
	
	async def update_status(self, *args, **kwargs):
		users = 0
		for guild in self.guilds:
			users += len(guild.members)
		
		await self.change_presence(activity=discord.Game(name=f'.help | {users} users'))

	async def on_command_error(self, ctx, exc):
		if hasattr(exc, 'original'):
			#if isinstance(exc, AssertionError) or issubclass(exc.__class__, commands.CommandError):
			#	return
			#log.error(exc.original)
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
			return # fuck these
		elif isinstance(exc, commands.CommandError):
			title = 'An error occured, specifically:'
			extra = str(exc)
		
		if extra is None:
			log.debug(f'Unhandled exception of type {type(exc)}: {str(exc)}')
			return
		
		await ctx.send(embed=discord.Embed(title=title, description=extra))
		
# monkey-patched Embed class to force embed color
class Embed(discord.Embed):
	def __init__(self, color=0x2E4D83, **attrs):
		attrs['color'] = color
		super().__init__(**attrs)

discord.Embed = Embed
		
if __name__ == '__main__':
	AceBot().run(token)