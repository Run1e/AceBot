import discord
from discord.ext import commands


class EmbedHelp:
	pass


class HelpCog:
	def __init__(self, bot):
		self.bot = bot

	@commands.command(hidden=True)
	async def help(self, ctx, *commands: str):
		bot = self.bot
		fmt = bot.formatter

		e = discord.Embed()


def setup(bot):
	bot.add_cog(HelpCog(bot))
