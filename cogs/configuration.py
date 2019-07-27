import discord
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.checks import is_mod
from utils.guildconfig import GuildConfig


class MemberID(commands.MemberConverter):
	async def convert(self, ctx, argument):
		pass  # TODO


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

	@commands.command()
	@commands.has_permissions(administrator=True)  # only allow administrators to change the moderator role
	async def modrole(self, ctx, *, role: discord.Role = None):
		'''Set the moderator role. Only editable by server administrators.'''

		gc = await GuildConfig.get_guild(ctx.guild.id)

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
			f'Mod role has been set to `{role.name}`. Members with this role can configure and manage the bot.'
		)

	@commands.command()
	@is_mod()
	async def prefix(self, ctx, *, prefix: PrefixConverter):
		'''Set a guild-specific prefix.'''

		guild = await GuildConfig.get_guild(ctx.guild.id)
		await guild.set('prefix', prefix)

		await ctx.send(
			f'Prefix set to `{prefix}`\nIf you forget your prefix, simply mention the bot to open up the help menu.'
		)


def setup(bot):
	bot.add_cog(GuildConfigurer(bot))
