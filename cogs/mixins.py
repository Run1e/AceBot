from discord.ext import commands


class AceMixin:
	def __init__(self, bot):
		self.bot = bot
		self.db = bot.db


class ToggleMixin:
	'''Mixin for making a cog toggleable.'''

	async def cog_check(self, ctx):
		return await self.bot.guild_uses_module(ctx.guild.id, self.__class__.__name__.lower())
