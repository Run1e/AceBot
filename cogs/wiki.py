import discord
from discord.ext import commands

import wikipedia

class Wiki:
	"""Admin commands"""

	def __init__(self, bot):
		self.bot = bot

	async def embedwiki(self, ctx, wiki):
		embed = discord.Embed()

		sum = wiki.summary
		if len(sum) > 1024:
			sum = sum[0:1024] + '...'

		embed.description = sum
		embed.set_author(name=wiki.title, url=wiki.url, icon_url='https://i.imgur.com/qIor1ag.png')

		image = ''
		for img in wiki.images:
			if not img.endswith('.svg'):
				image = img
				break

		if image:
			embed.set_image(url=image)

		embed.set_footer(text='wikipedia.com')
		await ctx.send(embed=embed)


	@commands.command(aliases=['wiki'], enabled=False)
	async def wikipedia(self, ctx, *, query):
		"""Preview a Wikipedia article."""

		await ctx.trigger_typing()

		try:
			wiki = wikipedia.page(query)
		except:
			return await ctx.send('No results.')

		await self.embedwiki(ctx, wiki)

	@commands.command(enabled=False)
	async def wikirandom(self, ctx):
		"""Get a random Wikipedia page."""

		await ctx.trigger_typing()
		try:
			page_name = wikipedia.random(1)
		except:
			return await ctx.invoke(self.wikirandom)

		try:
			wiki = wikipedia.page(page_name)
			for attr in ('summary', 'url', 'title'):
				if not hasattr(wiki, attr):
					return await ctx.invoke(self.wikirandom)
		except wikipedia.exceptions.DisambiguationError as e:
			return await ctx.invoke(self.wikirandom)
		await self.embedwiki(ctx, wiki)


def setup(bot):
	bot.add_cog(Wiki(bot))