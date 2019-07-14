import discord

from discord.ext import commands

from cogs.mixins import AceMixin



class Moderator(AceMixin, commands.Cog):
	'''Commands available to moderators. '''

	async def cog_check(self, ctx):
		return False

