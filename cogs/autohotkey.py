import discord
from discord.ext import commands

import requests
import json
import re
from bs4 import BeautifulSoup

from cogs.utils.docs_search import docs_search

class AutoHotkeyCog:
	"""Commands for the AutoHotkey server"""

	def __init__(self, bot):
		self.bot = bot
		self.guild_id = 115993023636176902

		self.pastes = {}

		# plain command responses
		self.plains = {
			'geekdude': 'Everyone does a stupid sometimes.',
			'hello': 'Hello {0.author.mention}!',
			'shrug': '¯\_(ツ)_/¯',
			'source': 'https://github.com/Run1e/A_AhkBot',
			('paste', 'p'): 'Paste your code at http://p.ahkscript.org/',
			('code', 'c'): 'Use the highlight command to paste code: !hl [paste code here]',
			('ask', 'a'): "Just ask your question, don't ask if you can ask!"
		}

		# simple reply
		self.replies = {
			'\o': 'o/',
			'o/': '\o'
		}

		# list of commands to ignore
		self.ignore_cmds = (
			'clear', 'mute', 'levels', 'rank', 'mute',
			'unmute', 'manga', 'pokemon', 'urban', 'imgur',
			'anime', 'twitch', 'youtube'
		)

		# list of users to ignore (like for example bots or people misusing the bot)
		self.ignore_users = (
			327874898284380161,
			155149108183695360,
			159985870458322944
		)

		# list of channels to ignore
		self.ignore_chan = (
			318691519223824384,
			296187311467790339
		)

	async def __local_check(self, ctx):
		# check if we're in the right server
		if not ctx.guild.id == self.guild_id:
			return False

		# check if message comes from bot
		if ctx.message.author.id == self.bot.user.id:
			return False

		# check if message author is in list of ignored users
		if ctx.message.author.id in self.ignore_users:
			return False

		# check if message channel is in list of ignored channels
		if ctx.message.channel.id in self.ignore_chan:
			return False

		return True

	async def on_message(self, message):
		# stop if we're running a "command"
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# get the message context
		ctx = await self.bot.get_context(message)

		# check if we're in the ahk server etc
		if not await self.__local_check(ctx):
			return

		# see if the message has a reply
		if message.content in self.replies:
			return await ctx.send(self.replies[message.content])

		# see if we can find any links
		try:
			link = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)[0]
		except:
			return

		# if so, post a preview of the forum or paste link
		if link.startswith("http://p.ahkscript.org/?"):
			return await self.pastelink(ctx, link)
		if link.startswith("https://autohotkey.com/boards/viewtopic.php?"):
			return await self.forumlink(ctx, link)

	async def on_command_error(self, ctx, error):
		# we're listening to CommandNotFound errors, so if the error is not one of those, print it
		if not isinstance(error, commands.CommandNotFound):
			print(error)
			return

		# check we're in the ahk sserver
		if not await self.__local_check(ctx):
			return

		# if it's a mee6 command, ignore it (don't docs search it)
		if ctx.invoked_with in self.ignore_cmds:
			return

		# special case, method names can't have + or - in them, which makes sense
		if ctx.invoked_with == 'helper+':
			return await self.helper(ctx, True)
		elif ctx.invoked_with == 'helper-':
			return await self.helper(ctx, False)

		# check if there's a simple text reply associated
		for key in self.plains:
			if ctx.invoked_with in key:
				return await ctx.send(self.plains[key].format(ctx))

		# if none of the above, search the documentation with the input
		await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def pastelink(self, ctx, link):
		link = link.replace("?p=", "?r=")
		link = link.replace("?e=", "?r=")

		req = requests.get(link)
		text = req.text

		if len(text) > 1920:
			return
		if text.count('\n') > 32:
			return

		await ctx.invoke(self.highlight, code=text)

	async def forumlink(self, ctx, link):
		if link.find('#'):
			link = re.sub('\#p\d*', '', link)
		link = re.sub('&start=\d*', '', link)

		req = requests.get(link)
		soup = BeautifulSoup(req.text, 'html.parser')

		title = soup.find('title').text

		await ctx.send(embed=discord.Embed(title=title, url=link))

	async def helper(self, ctx, add):
		role = discord.utils.get(ctx.guild.roles, name="Helpers")
		if add:
			await ctx.author.add_roles(role)
			await ctx.send('Added to Helpers!')
		else:
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
		await ctx.send(embed=discord.Embed(title='Tutorial by tidbit', description='https://autohotkey.com/docs/Tutorial.htm'))

	@commands.command(aliases=['hl'])
	async def highlight(self, ctx, *, code):
		"""Highlights some AutoHotkey code. Use !hl"""

		if ctx.invoked_with:
			await ctx.message.delete()

		try:
			self.pastes[ctx.author.id]
		except:
			self.pastes[ctx.author.id] = []

		msg = await ctx.send('```AutoIt\n{}\n```*{}, type `!del` to delete*'.format(code, ('Paste by {}' if ctx.invoked_with else "Paste from {}'s link").format(ctx.message.author.mention)))

		self.pastes[ctx.author.id].append(msg)

	@commands.command(aliases=['del'], hidden=True)
	async def delete(self, ctx):
		if ctx.author.id in self.pastes:
			try:
				message = self.pastes[ctx.author.id].pop()
			except:
				return await ctx.send('No paste to delete.')
			await message.delete()
			await ctx.message.delete()

	@commands.command(aliases=['download', 'update'])
	async def version(self, ctx):
		"""Get a download link to the latest AutoHotkey_L version."""

		req = requests.get('https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')
		version = json.loads(req.text)['tag_name']
		down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])

		embed = discord.Embed(title="<:ahk:317997636856709130> AutoHotkey_L", url=down)
		embed.set_footer(text="Latest version: {}".format(version))

		await ctx.send(embed=embed)

	@commands.command()
	async def studio(self, ctx):
		"""Returns a download link to AHK Studio."""

		req = requests.get('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')
		version = req.text.split('\r\n')[0]

		embed = discord.Embed(description='Feature rich IDE for AutoHotkey!\n[Direct download]({})'.format('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.ahk'))
		embed.set_author(name='AHK Studio', url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300', icon_url='https://i.imgur.com/DXtmUwN.png')

		embed.set_footer(text='Latest version: {}'.format(version))
		await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(AutoHotkeyCog(bot))