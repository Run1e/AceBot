import discord, logging
from discord.ext import commands
from sqlalchemy import and_

from utils.database import GuildModule
from utils.checks import is_manager

log = logging.getLogger(__name__)


class Configuration:
	'''
	Manage modules and other settings.
	
	Only users with Manage Server permission can toggle modules.
	'''

	def __init__(self, bot):
		self.bot = bot

	@commands.command(aliases=['mods'])
	@is_manager()
	@commands.bot_has_permissions(embed_links=True)
	async def modules(self, ctx):
		'''List modules.'''

		mods = await GuildModule.query.where(
			GuildModule.guild_id == ctx.guild.id
		).gino.all()

		mod_list = []

		for modu in mods:
			mod_list.append(modu.module)

		e = discord.Embed(
			description=(
				'`.enable <module>` to enable a module.\n'
				'`.disable <module>` to disable.\n'
				'`.help <module>` to see commands.'
			)
		)

		e.set_author(name='Modules', icon_url=self.bot.user.avatar_url)

		enabled = '\n'.join(mod_list)
		disabled = '\n'.join(filter(lambda mod: mod not in mod_list, self.bot._toggleable))

		e.add_field(name='Enabled', value=enabled if len(enabled) else 'None')
		e.add_field(name='Disabled', value=disabled if len(disabled) else 'None')

		await ctx.send(embed=e)

	@commands.command()
	@is_manager()
	async def enable(self, ctx, module: str):
		'''Enable a module.'''

		module = module.lower()
		if module not in self.bot._toggleable:
			raise commands.CommandError(f'Module `{module}` is not a valid module.')

		if await self.bot.uses_module(ctx.guild.id, module):
			return await ctx.send(f'Module `{module}` already enabled.')

		result = await GuildModule.create(
			guild_id=ctx.guild.id,
			module=module
		)

		if result is None:
			raise commands.CommandError(f'Failed enabling module `{module}`')

		log.info(f'{ctx.author.name} enabled \'{module}\' in {ctx.guild.name}')
		await ctx.send(f'Module `{module}` enabled.')

	@commands.command()
	@is_manager()
	async def disable(self, ctx, module: str):
		'''Disable a module.'''

		module = module.lower()

		if module not in self.bot._toggleable:
			raise commands.CommandError(f'{module} is not a valid module.')

		mod = await GuildModule.query.where(
			and_(
				GuildModule.guild_id == ctx.guild.id,
				GuildModule.module == module
			)
		).gino.first()

		if mod is None:
			return await ctx.send(f'Module `{module}` is not currently enabled.')

		res = await mod.delete()

		if res == 'DELETE 1':
			log.info(f'{ctx.author.name} disabled \'{module}\' in {ctx.guild.name}')
			await ctx.send(f'Module `{module}` disabled.')
		else:
			raise commands.CommandError(f'Failed disabling module `{module}`')


def setup(bot):
	bot.add_cog(Configuration(bot))
