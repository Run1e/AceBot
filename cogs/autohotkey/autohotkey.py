import discord
from discord.ext import commands

import requests
import json
import re
from bs4 import BeautifulSoup

from cogs.autohotkey.docs_search import docs_search
from cogs.search import search

class AutoHotkeyCog:
	def __init__(self, bot):
		self.bot = bot
		self.id = 115993023636176902
		self.embedcolor = 0x78A064

		self.trusted = (
			265644569784221696
		)

		self.pastes = {}

		self.plains = {
			"geekdude": "Everyone does a stupid sometimes.",
			"paste": "Paste your code at http://p.ahkscript.org/",
			"hello": "Hello {0.author.mention}!",
			"code": "Use the highlight command to paste code: !hl [paste code here]",
			"shrug": "¯\_(ツ)_/¯",
			"source": "https://github.com/Run1e/A_AhkBot",
			"ask": "Just ask your question, don't ask if you can ask!",
			"leaderboards": "https://mee6.xyz/levels/115993023636176902"
		}

		# for the lazy
		self.plain_assoc = {
			'a': 'ask',
			'lb': 'leaderboards',
			'p': 'paste',
			'c': 'code'
		}

		self.replies = {
			'\o': 'o/',
			'o/': '\o'
		}

		self.ignore_cmds = (
			'clear',
			'mute',
			'levels',
			'rank',
			'mute',
			'unmute',
			'manga',
			'pokemon',
			'urban',
			'imgur',
			'anime',
			'twitch',
			'youtube'
		)

		self.ignore_users = (
			327874898284380161,
			155149108183695360,
			159985870458322944
		)

		self.ignore_chan = (
			318691519223824384,
			296187311467790339
		)


	async def on_message(self, message):
		ctx = await self.bot.get_context(message)

		if not await self.__local_check(ctx):
			return

		if message.content in self.replies:
			return await ctx.send(self.replies[message.content])

		try:
			link = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)[0]
		except Exception:
			link = ''

		if link.startswith("http://p.ahkscript.org/?"):
			return await self.pastelink(ctx, link)
		if link.startswith("https://autohotkey.com/boards/viewtopic.php?"):
			return await self.forumlink(ctx, link)

	async def pastelink(self, ctx, link):
		link = link.replace("?p=", "?r=")
		link = link.replace("?e=", "?r=")

		req = requests.get(link)
		text = req.text

		if len(text) > 1920:
			return
		if text.count('\n') > 32:
			return

		await ctx.send("```AutoIt\n{}\n```*Paste by {}, automated paste from link.*".format(text, ctx.message.author.mention))

	async def forumlink(self, ctx, link):
		if link.find('#'):
			link = re.sub('\#p\d*', '', link)
		link = re.sub('&start=\d*', '', link)

		req = requests.get(link)
		soup = BeautifulSoup(req.text, 'html.parser')

		title = soup.find('title').text

		await ctx.send(embed=discord.Embed(title=title, url=link, color=self.embedcolor))

	async def __local_check(self, ctx):
		# check if we're in the right server
		if not ctx.guild.id == self.id:
			return

		# check if message comes from bot
		if ctx.message.author.id == self.bot.user.id:
			return

		# check if message author is in list of ignored users
		if ctx.message.author.id in self.ignore_users:
			return False

		# check if message channel is in list of ignored channels
		if ctx.message.channel.id in self.ignore_chan:
			return False

		# otherwise, check if we're in the right server
		return True

	async def on_command_error(self, ctx, error):
		if not isinstance(error, commands.CommandNotFound):
			print(error)
			return

		if not await self.__local_check(ctx):
			return

		if ctx.invoked_with in self.ignore_cmds:
			return

		# special case, method names can't have + or - in them, which makes sense
		if ctx.invoked_with == 'helper+':
			return await self.helper(ctx, True)
		elif ctx.invoked_with == 'helper-':
			return await self.helper(ctx, False)

		if ctx.invoked_with in self.plains:
			return await ctx.send(self.plains[ctx.invoked_with])

		if ctx.invoked_with in self.plain_assoc:
			return await ctx.send(self.plains[self.plain_assoc[ctx.invoked_with]])

		embed = docs_search(ctx.message.content[1:])
		if embed:
			await ctx.send(embed=embed)

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
		embed = docs_search(search)
		if embed:
			await ctx.send(embed=embed)

	@commands.command(aliases=['bow'], hidden=True)
	async def mae(self, ctx):
		await ctx.message.delete()
		await ctx.send('*' + ctx.author.mention + " bows*")

	@commands.command(hidden=True)
	async def documentation(self, ctx):
		await ctx.send(embed=discord.Embed(title='AutoHotkey documentation', description='https://autohotkey.com/docs/AutoHotkey.htm', color=self.embedcolor))

	@commands.command(hidden=True)
	async def forums(self, ctx):
		await ctx.send(embed=discord.Embed(title='AutoHotkey forums', description='https://autohotkey.com/boards/', color=self.embedcolor))

	@commands.command(aliases=['tut'], hidden=True)
	async def tutorial(self, ctx):
		await ctx.send(embed=discord.Embed(title='Tutorial by tidbit', description='https://autohotkey.com/docs/Tutorial.htm', color=self.embedcolor))

	@commands.command(aliases=['hl'])
	async def highlight(self, ctx, *, code):
		"""Highlights some AutoHotkey code. Use !hl"""
		await ctx.message.delete()
		try:
			self.pastes[ctx.author.id]
		except:
			self.pastes[ctx.author.id] = []
		self.pastes[ctx.author.id].append(await ctx.send("```AutoIt\n{}\n```*Paste by {}, type `!del` to delete*".format(code, ctx.message.author.mention)))

	@commands.command(aliases=['del'], hidden=True)
	async def delete(self, ctx):
		if ctx.author.id in self.pastes:
			try:
				message = self.pastes[ctx.author.id].pop()
			except:
				return await ctx.send('No paste to delete.')
			await message.delete()
			await ctx.message.delete()

	@commands.command(aliases=['f'], hidden=True)
	async def forum(self, ctx, *, input):
		if ctx.author.id not in self.trusted:
			return
		result = search('site:autohotkey.com ' + input)
		if result:
			await ctx.send(embed=discord.Embed(**result, color=self.embedcolor))

	@commands.command(aliases=['ahk', 'update'])
	async def version(self, ctx):
		"""Get a download link to the latest AutoHotkey_L version."""
		req = requests.get('https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')
		version = json.loads(req.text)['tag_name']
		down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])
		await ctx.send(embed=discord.Embed(title="<:ahk:317997636856709130> AutoHotkey_L", description="Latest version: {}".format(version), url=down, color=self.embedcolor))

	@commands.command()
	async def studio(self, ctx):
		"""Returns a download link to AHK Studio"""
		req = requests.get('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')
		version = req.text.split('\r\n')[0]
		embed = discord.Embed(title='<:studio:317999706087227393> AHK Studio', description='Latest version: ' + version, url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300', color=self.embedcolor)
		await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(AutoHotkeyCog(bot))