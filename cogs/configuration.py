import discord
from discord.ext import commands

from config import DEFAULT_PREFIX
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
	async def prefix(self, ctx, *, prefix: PrefixConverter = None):
		'''Set a guild-specific prefix. Call `prefix` to clear.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		await gc.update(prefix=prefix)

		await ctx.send(
			f'Prefix set to `{prefix or DEFAULT_PREFIX}` - if you forget your prefix, '
			'simply mention the bot to open up the help menu.'
		)

	@commands.command()
	@commands.has_permissions(administrator=True)  # only allow administrators to change the moderator role
	async def modrole(self, ctx, *, role: discord.Role = None):
		'''Set the moderator role. Only modifiable by server administrators. Call `modrole` to clear.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		if role is None:
			gc.mod_role_id = None
			await ctx.send('Mod role cleared.')
		else:
			gc.mod_role_id = role.id
			await ctx.send(
				f'Mod role has been set to `{role.name}` ({role.id}). '
				'Members with this role can configure and manage the bot.'
			)

		await gc.update()


def setup(bot):
	bot.add_cog(Configuration(bot))
