from discord.ext import commands

from utils.guildconfig import GuildConfig

class AceMixin:
	def __init__(self, bot):
		self.bot = bot
		self.db = bot.db


class ToggleMixin:
	'''Mixin for making a cog toggleable.'''

	async def cog_check(self, ctx):
		guild = await GuildConfig.get_guild(ctx.guild.id)
		return await guild.uses_module(self.__class__.__name__.lower())
