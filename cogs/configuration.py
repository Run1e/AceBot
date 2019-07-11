import discord
from discord.ext import commands

from cogs.mixins import AceMixin, ToggleMixin
from utils.guildconfig import GuildConfig


"""
guild config menu:
- prefix
- module disable/enable
- role that can moderate the bot
"""

"""
db:


"""

class MemberID(commands.MemberConverter):
	async def convert(self, ctx, argument):
		pass # TODO

class ModuleConverter(commands.Converter):
	async def convert(self, ctx, module):
		for cog_name, cog in ctx.bot.cogs.items():
			cog_name = cog_name.lower()
			if cog_name == module and isinstance(cog, ToggleMixin):
				return cog_name

		raise commands.CommandError(f'Unknown module \'{module}\'')

class PrefixConverter(commands.Converter):
	async def convert(self, ctx, prefix):
		if len(prefix) > 8 or len(prefix) < 1:
			raise commands.CommandError('Prefix must be between 1 and 8 characters.')

		# TODO: add checks for no markdown?

		return prefix

class SettingConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass

class GuildConfigurer(AceMixin, commands.Cog):

	async def cog_check(self, ctx):
		# TODO: add checks for configers

		return True

	@commands.command(aliases=['mods'])
	async def modules(self, ctx):
		'''Lists enabled modules.'''

		enabled_mods = list(
			r.get('module') for r in
			await self.db.fetch('SELECT module FROM module WHERE guild_id=$1', ctx.guild.id)
		)

		disabled_mods = list(
			cog_name.lower() for cog_name, cog in self.bot.cogs.items()
			if isinstance(cog, ToggleMixin) and cog_name.lower() not in enabled_mods
		)

		prefix = await self.bot.prefix_resolver(self.bot, ctx.message)

		e = discord.Embed(
			description=(
				f'`{prefix}enable <module>` to enable a module.\n'
				f'`{prefix}disable <module>` to disable.\n'
				f'`{prefix}help <module>` to see commands.'
			)
		)

		e.set_author(name='Modules', icon_url=self.bot.user.avatar_url)

		enabled = '\n'.join(enabled_mods)
		disabled = '\n'.join(disabled_mods)

		e.add_field(name='Enabled', value=enabled if len(enabled) else 'None')
		e.add_field(name='Disabled', value=disabled if len(disabled) else 'None')

		await ctx.send(embed=e)

	@commands.command()
	async def enable(self, ctx, module: ModuleConverter):
		'''Enable a module.'''

		guild = await GuildConfig.get_guild(ctx.guild.id)
		if await guild.enable_module(module):
			await ctx.send(f'Module \'{module}\' enabled.')
		else:
			await ctx.send('Module already enabled.')

	@commands.command()
	async def disable(self, ctx, module: ModuleConverter):
		'''Disable a module.'''

		guild = await GuildConfig.get_guild(ctx.guild.id)
		if await guild.disable_module(module):
			await ctx.send(f'Module \'{module}\' disabled.')
		else:
			await ctx.send('Module not previously enabled.')


	@commands.command()
	async def prefix(self, ctx, prefix: PrefixConverter):
		'''Set a guild-specific prefix.'''

		guild = await GuildConfig.get_guild(ctx.guild.id)
		await guild.set_prefix(prefix)




def setup(bot):
	bot.add_cog(GuildConfigurer(bot))