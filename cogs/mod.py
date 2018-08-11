import discord
from discord.ext import commands


class Moderator:
	"""Admin commands"""

	def __init__(self, bot):
		self.bot = bot

	async def __local_check(self, ctx):
		return ctx.author.permissions_in(ctx.channel).manage_messages

	@commands.command()
	async def clear(self, ctx, message_count: int = None, user: discord.User = None):
		"""Clear x amount of messages, either from user or just indiscriminately."""

		if message_count is None:
			return await ctx.send('Please choose a message count.')

		if message_count > 50:
			return await ctx.send('Please choose a message count below 50.')

		if user is not None:
			check = lambda msg: msg.author == user
		else:
			check = None

		await ctx.message.delete()
		await ctx.channel.purge(limit=message_count, check=check)


def setup(bot):
	bot.add_cog(Moderator(bot))
