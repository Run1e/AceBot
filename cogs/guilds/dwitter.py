import discord
from discord.ext import commands

import re

class Dwitter:
	"""Commands for the Dwitter server."""

	def __init__(self, bot):
		self.bot = bot

	async def __local_check(self, ctx):
		return ctx.guild.id in (395956681793863690,) or await self.bot.is_owner(ctx.author)

	async def on_message(self, message):
		# ignore messages that start with a prefix
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# get context and do checks
		ctx = await self.bot.get_context(message)
		if not (await self.__local_check(ctx) and await self.bot.can_run(ctx)):
			return

		# find links in message
		try:
			links = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
		except:
			return

		# loop through links and send previews if applicable
		for index, link in enumerate(links):
			if (index > 2):
				break
			if re.match("^https?://(www.)?dwitter.net/d/", link):
				await self.dwitterlink(ctx, link)

	async def dwitterlink(self, ctx, link):
		print(link)


def setup(bot):
	bot.add_cog(Dwitter(bot))