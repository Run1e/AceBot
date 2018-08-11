from discord.ext import commands

import re


class Highlighter:
	"""Handles the highlight command."""

	def __init__(self, bot):
		self.bot = bot
		self.default = 'autoit'
		self.guilds = {
			395956681793863690: 'js',
			330423308103319562: 'cs'
		}

	async def on_reaction_add(self, reaction, user):
		pattern = f'^```{self.guilds[reaction.message.guild.id] if reaction.message.guild.id in self.guilds else self.default}(\s|.)*, click the cross to delete\.\*$'
		if user == self.bot.user or not re.search(pattern, reaction.message.content):
			return

		author = reaction.message.mentions[0]

		if (author == user or user.permissions_in(
				reaction.message.channel).manage_messages) and reaction.emoji == '\U0000274C':
			print(f'\n{author} del highlight')
			await reaction.message.delete()
		else:
			await reaction.message.remove_reaction(reaction, user)

	@commands.command(aliases=['h1'])
	async def hl(self, ctx, *, code):
		"""Highlights some code."""

		code = ctx.message.content[4:]

		# don't paste if there's hella many backticks fam
		if '```' in code:
			return

		# if it was invoked (by a user) we delete the source message
		if ctx.invoked_with:
			await ctx.message.delete()

		msg = await ctx.send('```{}\n{}\n```*{}, click the cross to delete.*'.format(
			self.guilds[ctx.guild.id] if ctx.guild.id in self.guilds else self.default, code,
			('Paste by {}' if ctx.invoked_with else "Paste from {}'s link").format(ctx.message.author.mention)))

		await msg.add_reaction('\U0000274C')

	@commands.command(aliases=['p'], hidden=True)
	async def paste(self, ctx):
		msg = 'To paste code snippets directly into the chat, use the highlight command:\n```.hl *paste code here*```'
		if (ctx.guild.id == 115993023636176902):
			msg += 'If you have a larger script you want to share, paste it to the AutoHotkey pastebin instead:\nhttp://p.ahkscript.org/'
		await ctx.send(msg)


def setup(bot):
	bot.add_cog(Highlighter(bot))
