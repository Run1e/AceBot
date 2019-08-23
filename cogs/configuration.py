import discord
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.checks import is_mod


class PrefixConverter(commands.Converter):
	async def convert(self, ctx, prefix):
		if len(prefix) > 8 or len(prefix) < 1:
			raise commands.CommandError('Prefix must be between 1 and 8 characters.')

		if prefix != discord.utils.escape_markdown(prefix):
			raise commands.CommandError('No markdown allowed in prefix.')

		return prefix


class SettingConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass


class Configuration(AceMixin, commands.Cog):
	'''Bot configuration available to administrators and people in the moderator role.'''

	@commands.command()
	@is_mod()
	async def prefix(self, ctx, *, prefix: PrefixConverter):
		'''Set a guild-specific prefix.'''

		guild = await self.bot.config.get_entry(ctx.guild.id)
		await guild.set('prefix', prefix)

		await ctx.send(
			f'Prefix set to `{prefix}` - if you forget your prefix, simply mention the bot to open up the help menu.'
		)

	@commands.command()
	@commands.has_permissions(administrator=True)  # only allow administrators to change the moderator role
	async def modrole(self, ctx, *, role: discord.Role = None):
		'''Set the moderator role. Only modifiable by server administrators.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		if role is None:
			role_id = gc.mod_role_id
			if role_id is None:
				raise commands.CommandError('Mod role not set.')

			role = ctx.guild.get_role(role_id)
			if role is None:
				raise commands.CommandError('Mod role set but not found. Try setting it again.')
		else:
			await gc.set('mod_role_id', role.id)

		await ctx.send(
			f'Mod role has been set to `{role.name}` ({role.id}). Members with this role can configure and manage the bot.'
		)


def setup(bot):
	bot.add_cog(Configuration(bot))
