import discord
from discord.ext import commands

import re
import random

from cogs.utils.docs_search import docs_search
from cogs.utils.shorten import shorten
import cogs.utils.ahk_forum as Preview

class AutoHotkey:
	"""Commands for the AutoHotkey server"""

	def __init__(self, bot):
		self.bot = bot
		self.guilds = (115993023636176902, 317632261799411712)

	# make sure we're in the the correct guild(s)
	async def __local_check(self, ctx):
		return getattr(ctx.guild, 'id', None) in self.guilds

	async def on_message(self, message):
		# guild check
		if not await self.__local_check(message):
			return

		# run blacklist test
		if self.bot.blacklist(message):
			return

		# ignore messages that start with a prefix
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# find links in message
		try:
			links = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
		except:
			return

		# loop through links and send previews if applicable
		seen = []
		for link in links:
			if len(seen) > 2:
				break
			if link in seen:
				continue
			if re.match("^https?://(www.)?p.ahkscript.org/\?", link):
				seen.append(link)
				await self.pastelink(message, link)
			if re.match("^https?://(www.)?autohotkey.com/boards/viewtopic.php\?", link):
				seen.append(link)
				await self.forumlink(message, link)

	async def on_command_error(self, ctx, error):
		if not await self.__local_check(ctx) or not await self.bot.can_run(ctx):
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and not re.search('^\.{2}', ctx.message.content):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def pastelink(self, message, url):
		url = url.replace("?p=", "?r=")
		url = url.replace("?e=", "?r=")

		text = await self.bot.request('get', url)

		if text is None:
			return

		if len(text) > 2048 or text.count('\n') > 24:
			return

		ctx = await self.bot.get_context(message)
		await ctx.invoke(self.bot.get_command('highlight'), code=text)

	# ty capn!
	async def forumlink(self, message, url):
		tempurl = re.sub("&start=\d+$", "", url)

		text = await self.bot.request('get', tempurl)

		if text is None:
			return

		post = Preview.getThread(url, text)
		embed = discord.Embed(title=post["title"], url=url)
		embed.description = shorten(post['description'], 2048, 12)
		if post["image"]:
			embed.set_image(url=post["image"] if post["image"][0] != "." else "https://autohotkey.com/boards" + post["image"][1:post["image"].find("&") + 1])
		embed.set_author(name=post["user"]["name"], url="https://autohotkey.com/boards" + post["user"]["url"][1:],
						 icon_url="https://autohotkey.com/boards" + post["user"]["icon"][1:])
		embed.set_footer(text='autohotkey.com')

		await message.channel.send(embed=embed)

	@commands.command()
	async def docs(self, ctx, *, search):
		"""Search the documentation."""
		result = docs_search(search)
		embed = discord.Embed()
		if 'fields' in result:
			for field in result['fields']:
				embed.add_field(**field)
		else:
			embed.title = result['title']
			embed.description = result['description']
			if 'url' in result:
				embed.url = result['url']
		if embed:
			await ctx.send(embed=embed)

	@commands.command(aliases=['download', 'update'])
	async def version(self, ctx):
		"""Get a download link to the latest AutoHotkey_L version."""

		data = await self.bot.request('get', 'https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')

		if data is None:
			return

		version = data['tag_name']

		down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])

		embed = discord.Embed(title="<:ahk:317997636856709130> AutoHotkey_L", url=down)
		embed.set_footer(text="Latest version: {}".format(version))

		await ctx.send(embed=embed)

	@commands.command()
	async def studio(self, ctx):
		"""Returns a download link to AHK Studio."""

		text = await self.bot.request('get', 'https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')

		if text is None:
			return

		version = text.split('\r\n')[0][:-1]

		embed = discord.Embed(description='Feature rich IDE for AutoHotkey!')
		embed.set_author(name='AHK Studio', url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300', icon_url='https://i.imgur.com/DXtmUwN.png')
		embed.set_footer(text='Latest version: {}'.format(version))

		await ctx.send(embed=embed)

	@commands.command(aliases=['bow'], hidden=True)
	async def mae(self, ctx):
		await ctx.message.delete()
		await ctx.send('*' + ctx.author.mention + " bows*")

def setup(bot):
	bot.add_cog(AutoHotkey(bot))