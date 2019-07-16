import discord
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.checks import is_mod_pred
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

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	@commands.command()
	@commands.has_permissions(administrator=True)  # only allow administrators to change the moderator role
	async def modrole(self, ctx, *, role: discord.Role = None):
		'''Set the moderator role. Only editable by server administrators.'''

		gc = await GuildConfig.get_guild(ctx.guild.id)



	@commands.command()
	async def prefix(self, ctx, *, prefix: PrefixConverter):
		'''Set a guild-specific prefix.'''

		guild = await GuildConfig.get_guild(ctx.guild.id)
		await guild.set('prefix', prefix)

		await ctx.send(
			f'Prefix set to `{prefix}`\nIf you forget your prefix, simply mention the bot to open up the help menu.'
		)


def setup(bot):
	bot.add_cog(GuildConfigurer(bot))
