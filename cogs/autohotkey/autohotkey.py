import discord
from discord.ext import commands

import requests

from cogs.autohotkey.docs_search import docs_search
from cogs.search import search

class AutoHotkeyCog:
	def __init__(self, bot):
		self.bot = bot
		self.id = 115993023636176902

		self.pastes = {}

		self.plains = {
			"geekdude": "Everyone does a stupid sometimes."
			, "paste": "Paste your code at http://p.ahkscript.org/"
			, "hello": "Hello {0.author.mention}!"
			, "mae": "*{0.author.mention} bows*"
			, "code": "Use the highlight command to paste code: !hl [paste code here]"
			, "shrug": "¯\_(ツ)_/¯"
			, "source": "https://github.com/Run1e/A_AhkBot"
			, "ask": "Just ask your question, don't ask if you can ask!"
			, "leaderboards": "https://mee6.xyz/levels/115993023636176902"
		}

		# for the lazy
		self.plain_assoc = {
			'a': 'ask'
			, 'lb': 'leaderboards'
			, 'p': 'paste'
		}

		self.ignore_cmds = (
			'clear'
			, 'mute'
			, 'levels'
			, 'rank'
			, 'mute'
			, 'unmute'
			, 'manga'
			, 'pokemon'
			, 'urban'
			, 'imgur'
			, 'anime'
			, 'twitch'
			, 'youtube'
		)

		self.ignore_users = (
			327874898284380161
			, 155149108183695360
			, 159985870458322944
		)

		self.ignore_chan = (
			318691519223824384
			, 296187311467790339
		)

	async def __local_check(self, ctx):
		if ctx.message.author.id in self.ignore_users:
			return False
		if ctx.message.channel.id in self.ignore_chan:
			return False
		return ctx.guild.id == self.id

	async def on_command_error(self, ctx, error):
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

	@commands.command(aliases=['bow'], hidden=True)
	async def mae(self, ctx):
		await ctx.message.delete()
		await ctx.send('*' + ctx.author.mention + " bows*")

	@commands.command(hidden=True)
	async def documentation(self, ctx):
		await ctx.send(embed=discord.Embed(title='AutoHotkey documentation', description='https://autohotkey.com/docs/AutoHotkey.htm', color=0x78A064))

	@commands.command(hidden=True)
	async def forums(self, ctx):
		await ctx.send(embed=discord.Embed(title='AutoHotkey forums', description='https://autohotkey.com/boards/', color=0x78A064))

	@commands.command(aliases=['tut'], hidden=True)
	async def tutorial(self, ctx):
		await ctx.send(embed=discord.Embed(title='Tutorial by tidbit', description='https://autohotkey.com/docs/Tutorial.htm', color=0x78A064))

	@commands.command(aliases=['hl'])
	async def highlight(self, ctx, *, code):
		"""Highlights some AutoHotkey code."""
		await ctx.message.delete()
		self.pastes[ctx.author.id] = await ctx.send("```AutoIt\n{}\n```*Paste by {}, type `!del` to delete*".format(code, ctx.message.author.mention))

	@commands.command(aliases=['del'], hidden=True)
	async def delete(self, ctx):
		if ctx.author.id in self.pastes:
			message = self.pastes.pop(ctx.author.id)
			await message.delete()
			await ctx.message.delete()

	@commands.command(aliases=['f'], hidden=True)
	async def forum(self, ctx, *, input):
		if ctx.author.id != 265644569784221696:
			return
		result = search('site:autohotkey.com ' + input)
		if result:
			await ctx.send(embed=discord.Embed(**result, color=0x78A064))

	@commands.command(aliases=['ahk', 'update'])
	async def version(self, ctx):
		"""Get a download link to the latest AutoHotkey_L version."""
		req = requests.get('https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')
		version = json.loads(req.text)['tag_name']
		down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])
		await ctx.send(embed=discord.Embed(title="<:ahk:317997636856709130> AutoHotkey_L", description="Latest version: {}".format(version), url=down, color=0x78A064))

	@commands.command()
	async def studio(self, ctx):
		"""Returns a download link to AHK Studio"""
		req = requests.get('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')
		version = req.text.split('\r\n')[0]
		embed = discord.Embed(title='<:studio:317999706087227393> AHK Studio', description='Latest version: ' + version, url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300', color=0x78A064)
		await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(AutoHotkeyCog(bot))