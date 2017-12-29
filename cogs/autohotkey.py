import discord
from discord.ext import commands

import re

from cogs.utils.docs_search import docs_search
from cogs.utils.shorten import shorten
import cogs.utils.ahk_forum as Preview

class AutoHotkey:
	"""Commands for the AutoHotkey server"""

	def __init__(self, bot):
		self.bot = bot

	# make sure we're in the the correct guild(s)
	async def __local_check(self, ctx):
		return ctx.guild.id in (115993023636176902, 317632261799411712, 372163679010947074, 380066879919751179) or await self.bot.is_owner(ctx.author)

	async def on_member_join(self, member):
		if not member.guild.id == 115993023636176902:
			return

		channel = self.bot.get_channel(339511161672302593)
		await channel.send(f"Hi {member.mention}! Welcome to the official ***AutoHotkey*** server!\n"
						   "You won't be able to speak for about 10 minutes. Please spend this time reading the rules and tips at <#304708649748660224>.\n"
						   "If you come with a problem, also spend some time figuring out how to ask your question in a descriptive and thorough way so that people are able to help!\n"
						   "Happy scripting and we hope you enjoy your stay!")


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
			if (index > 1):
				break
			if re.match("^https?://(www.)?p.ahkscript.org/\?", link):
				await self.pastelink(ctx, link)
			if re.match("^https?://(www.)?autohotkey.com/boards/viewtopic.php\?", link):
				await self.forumlink(ctx, link)

	async def on_command_error(self, ctx, error):
		if not await self.__local_check(ctx):
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and not re.search('^\.{2}', ctx.message.content):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def pastelink(self, ctx, url):
		url = url.replace("?p=", "?r=")
		url = url.replace("?e=", "?r=")

		text = await self.bot.request('get', url)
		if text is None:
			return

		if len(text) > 2048 or text.count('\n') > 24:
			return

		await ctx.invoke(self.bot.get_command('highlight'), code=text)

	# ty capn!
	async def forumlink(self, ctx, url):
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

		await ctx.send(embed=embed)

	@commands.command(hidden=True)
	async def test(self, ctx):
		return await ctx.send(f"Hi {ctx.author.mention}! Welcome to the official ***AutoHotkey*** server!\n"
						   "You won't be able to speak for about 10 minutes. Please spend this time reading the rules and tips at <#304708649748660224>.\n"
						   "If you come with a problem, also spend some time figuring out how to ask your question in a descriptive and thorough way so that people are able to help!\n"
						   "Happy scripting and we hope you enjoy your stay!")

	@commands.command(name='helper+')
	async def helperplus(self, ctx):
		"""Add yourself to the Helper role."""
		role = discord.utils.get(ctx.guild.roles, name="Helpers")
		await ctx.author.add_roles(role)
		await ctx.send('Added to Helpers!')

	@commands.command(name='helper-')
	async def helperminus(self, ctx):
		"""Remove yourself from the Helper role."""
		role = discord.utils.get(ctx.guild.roles, name="Helpers")
		await ctx.author.remove_roles(role)
		await ctx.send('Removed from Helpers.')

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

		embed = discord.Embed(description='Feature rich IDE for AutoHotkey!\n[Direct download]({})'.format('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.ahk'))
		embed.set_author(name='AHK Studio', url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300', icon_url='https://i.imgur.com/DXtmUwN.png')

		embed.set_footer(text='Latest version: {}'.format(version))
		await ctx.send(embed=embed)

	@commands.command(hidden=True)
	@commands.has_permissions(kick_members=True)
	async def rule(self, ctx, rule: int, user):
		rules = (
			"**1. Be nice to eachother.**\nTreat others like you want others to treat you. Be nice.",
			"**2. Keep conversations civil.**\nDisagreeing is fine, but when it becomes a heated and unpleasant argument it will not be tolerated.",
			"**3. Don't post NSFW or antagonizing content.**\nThis includes but is not limited to nudity, sexual content, gore, personal information or disruptive content.",
			"**4. Don't spam/flood voice or text channels.**\nRepeated posting of text, links, images, videos or abusing the voice channels is not allowed.",
			"**5. No one is required or expected to help you.**\nIf no one wants to help you with your script, tough luck. Acting like a baby because of it will get you kicked/banned.",
			"**6. Do not tag individuals for help.**\nIf you're asking for help, you have to use the Helpers tag."
		)
		await ctx.message.delete()
		if rule > len(rules) or rule < 1:
			return
		await ctx.send(f'{user}\n\n{rules[rule - 1]}')

	@commands.command(hidden=True)
	async def geekdude(self, ctx):
		await ctx.send('Everyone does a stupid sometimes.')

	@commands.command(aliases=['a'], hidden=True)
	async def ask(self, ctx):
		await ctx.send("Just ask your question, don't ask whether you *can* ask!")

	@commands.command(aliases=['bow'], hidden=True)
	async def mae(self, ctx):
		await ctx.message.delete()
		await ctx.send('*' + ctx.author.mention + " bows*")

	@commands.command(hidden=True)
	async def documentation(self, ctx):
		await ctx.send(embed=discord.Embed(title='AutoHotkey documentation', description='https://autohotkey.com/docs/AutoHotkey.htm'))

	@commands.command(hidden=True)
	async def forums(self, ctx):
		await ctx.send(embed=discord.Embed(title='AutoHotkey forums', description='https://autohotkey.com/boards/'))

	@commands.command(aliases=['tut'], hidden=True)
	async def tutorial(self, ctx):
		await ctx.send('Tutorial by tidbit: https://autohotkey.com/docs/Tutorial.htm')

	@commands.command(hidden=True)
	async def tias(self, ctx):
		await ctx.send('http://i.imgur.com/6A6tcD0.png')

def setup(bot):
	bot.add_cog(AutoHotkey(bot))