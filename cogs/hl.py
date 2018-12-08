import discord, asyncio
from discord.ext import commands
from sqlalchemy.sql.operators import and_, or_

from cogs.base import TogglableCogMixin
from utils.strip_markdown import strip_markdown
from utils.checks import is_manager
from utils.database import HighlightLang


def make_lower(s: str): return s.lower()


class LangConverter(commands.Converter):
	_length_limit = 32

	async def convert(self, ctx, lang: make_lower):
		if len(lang) > self._length_limit:
			raise commands.CommandError(f'Preferred languages cannot be longer than {self._length_limit} characters.')
		if '\n' in lang:
			raise commands.CommandError('No newlines in preferred languages.')
		if '`' in lang:
			raise commands.CommandError('No backticks in preferred languages.')
		if lang != strip_markdown(lang):
			raise commands.CommandError('Markdown not allowed in tag names.')
		return lang


class Highlighter(TogglableCogMixin):
	'''Easily highlight code.'''

	timeout = 2
	emoji = '\U0000274C'
	language = 'python'
	messages = {}

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_raw_reaction_add(self, payload):

		if payload.message_id not in self.messages:
			return

		# ignore ourselves
		if payload.user_id == self.bot.user.id:
			return

		member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
		channel = self.bot.get_channel(payload.channel_id)
		message = await channel.get_message(payload.message_id)

		if not all([member, channel, message]):
			return

		# remove off-topic emojis
		if str(payload.emoji) == self.emoji and (
						payload.user_id == self.messages[payload.message_id] or member.permissions_in(
					channel).manage_messages):
			del self.messages[payload.message_id]
			await message.delete()
		else:
			await message.remove_reaction(payload.emoji, member)

	@commands.command(aliases=['h1'])
	@commands.bot_has_permissions(manage_messages=True, add_reactions=True)
	async def hl(self, ctx, *, code):
		'''Highlight some code.'''

		code = ctx.message.clean_content[4:]

		await ctx.message.delete()

		lang = await self.get_lang(ctx.guild.id, ctx.author.id)

		msg = await ctx.send(f'```{lang}\n{code}```Paste by {ctx.author.mention} - Click the {self.emoji} to delete.')

		await msg.add_reaction('\U0000274C')

		self.messages[msg.id] = ctx.author.id

	async def get_lang(self, guild_id, user_id):
		langs = await HighlightLang.query.where(
			and_(
				HighlightLang.guild_id == guild_id,
				or_(
					HighlightLang.user_id == user_id,
					HighlightLang.user_id == None
				)
			)
		).gino.all()

		selected = None
		for lang in langs:
			if lang.user_id is not None:
				return lang.language
			selected = lang.language

		return selected or self.language

	@commands.command()
	@is_manager()
	async def guildlang(self, ctx, *, language: LangConverter):
		'''Set the default guild highlighting language.'''

		server = await HighlightLang.query.where(
			and_(
				HighlightLang.guild_id == ctx.guild.id,
				HighlightLang.user_id == None
			)
		).gino.first()

		if server is None:
			await HighlightLang.create(
				guild_id=ctx.guild.id,
				language=language)
		else:
			await server.update(language=language).apply()

		await ctx.send(f'Guild language preference set to `{language}`')

	@commands.command()
	async def lang(self, ctx, *, language: LangConverter = None):
		'''Set your preferred highlighting language.'''

		personal = await HighlightLang.query.where(
			and_(
				HighlightLang.guild_id == ctx.guild.id,
				HighlightLang.user_id == ctx.author.id
			)
		).gino.first()

		if language is None:
			server = await self.get_lang(ctx.guild.id, None)

			e = discord.Embed(description='Do `.lang clear` to clear preference.')

			e.add_field(
				name='Server setting',
				value=f'`{self.language if server is None else server}`'
			)

			e.add_field(
				name='Personal setting',
				value='None' if personal is None else f'`{personal.language}`'
			)

			await ctx.send(embed=e)
			return

		if personal is None:
			await HighlightLang.create(
				guild_id=ctx.guild.id,
				user_id=ctx.author.id,
				language=language)
		else:
			if language == 'clear':
				await personal.delete()
				await ctx.send('Language preference cleared.')
				return
			else:
				await personal.update(language=language).apply()

		await ctx.send(f'Language preference set to `{language}`')

	@commands.command(aliases=['p'], hidden=True)
	async def paste(self, ctx):
		msg = 'To paste code snippets directly into the chat, use the highlight command:\n```.hl *paste code here*```'
		if ctx.guild.id == 115993023636176902:
			msg += (
				'If you have a larger script you want to share, paste it to the AutoHotkey pastebin instead:\n'
				'http://p.ahkscript.org/'
			)
		await ctx.send(msg)


def setup(bot):
	bot.add_cog(Highlighter(bot))
