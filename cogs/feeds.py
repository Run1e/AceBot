import discord

from discord.ext import commands

from cogs.mixins import AceMixin


class FeedConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass


class Feeds(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

	async def sub(self, ctx, *, feed: FeedConverter):
		'''Subscribe to a feed.'''

	async def publish(self, ctx, feed: FeedConverter, *, content: str):
		'''Publish to a feed.'''



def setup(bot):
	bot.add_cog(Feeds(bot))
