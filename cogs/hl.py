import discord
from discord.ext import commands

from cogs.ahk.ids import AHK_GUILD_ID
from cogs.mixins import AceMixin, ToggleMixin

DELETE_EMOJI = '\U0000274C'
DEFAULT_LANG = 'python'


class LangConverter(commands.Converter):
	async def convert(self, ctx, argument):
		if len(argument) < 1:
			raise commands.CommandError('Argument too short.')
		if len(argument) > 32:
			raise commands.CommandError('Argument too long.')

		return argument


class Highlighter(AceMixin, ToggleMixin, commands.Cog):

	async def get_lang(self, guild_id, user_id):
		'''Gets a users chosen highlighting language.'''

		lang = await self.db.fetchval(
			'SELECT lang FROM highlightlang WHERE guild_id=$1 AND (user_id=$2 OR user_id=$3)',
			guild_id, 0, user_id
		)

		return lang or DEFAULT_LANG

	@commands.command(aliases=['h1'])
	async def hl(self, ctx, *, code):
		'''Highlight some code.'''

		await ctx.message.delete()

		# include spaces/tabs at the beginning
		code = ctx.message.content[ctx.message.content.find(' ') + 1:]

		# don't allow three backticks in a row, alternative is to throw error upon this case
		code = code.replace('```', '`\u200b``')

		# get the language this user should use
		lang = await self.get_lang(ctx.guild.id, ctx.author.id)

		message = await ctx.send(
			f'```{lang}\n{code}\n```Paste by {ctx.author.mention} - Click the {DELETE_EMOJI} to delete.'
		)

		await self.db.execute(
			'INSERT INTO highlightmessage (message_id, author_id) VALUES ($1, $2)',
			message.id, ctx.author.id
		)

		await message.add_reaction(DELETE_EMOJI)

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		'''Listens for raw reactions and removes a highlighed message if appropriate.'''

		if payload.user_id == self.bot.user.id or str(payload.emoji) != DELETE_EMOJI:
			return

		if await self.db.execute(
			'DELETE FROM highlightmessage WHERE message_id=$1 AND author_id=$2'
			, payload.message_id, payload.user_id
		) == 'DELETE 0':
			return

		channel = self.bot.get_channel(payload.channel_id)
		if channel is None:
			return

		message = await channel.fetch_message(payload.message_id)
		if message is None:
			return

		await message.delete()

	@commands.command()
	async def lang(self, ctx, *, language: LangConverter = None):
		'''Set your preferred highlighting language in this server.'''

		if language is None:
			server_lang = await self.db.fetchval(
				'SELECT lang FROM highlightlang WHERE guild_id=$1 AND user_id=$2',
				ctx.guild.id, 0
			)

			user_lang = await self.db.fetchval(
				'SELECT lang FROM highlightlang WHERE guild_id=$1 AND user_id=$2',
				ctx.guild.id, ctx.author.id
			)

			e = discord.Embed(description='Do `.lang clear` to clear preference.')

			e.add_field(
				name='Server setting',
				value=f'`{DEFAULT_LANG if server_lang is None else server_lang}`'
			)

			e.add_field(
				name='Personal setting',
				value='Not set' if user_lang is None else f'`{user_lang}`'
			)

			await ctx.send(embed=e)
			return

		if language == 'clear':
			ret = await self.db.execute(
				'DELETE FROM highlightlang WHERE guild_id=$1 AND user_id=$2',
				ctx.guild.id, ctx.author.id
			)

			await ctx.send('No preference previously set' if ret == 'DELETE 0' else 'Preference cleared.')
		else:
			await self.db.execute(
				'INSERT INTO highlightlang (guild_id, user_id, lang) VALUES ($1, $2, $3) ON CONFLICT '
				'(guild_id, user_id) DO UPDATE SET lang=$3',
				ctx.guild.id, ctx.author.id, language
			)

			await ctx.send(f'Set your specific highlighting language to \'{language}\'.')

	@commands.command(aliases=['guildlang'])
	async def serverlang(self, ctx, *, language: LangConverter):
		'''Set a guild-specific highlighting language. Can be overridden individually by users.'''

		if language == 'clear':
			ret = await self.db.execute(
				'DELETE FROM highlightlang WHERE guild_id=$1 AND user_id=$2',
				ctx.guild.id, 0
			)

			await ctx.send('No preference previously set' if ret == 'DELETE 0' else 'Preference cleared.')
		else:
			await self.db.execute(
				'INSERT INTO highlightlang (guild_id, user_id, lang) VALUES ($1, $2, $3) ON CONFLICT '
				'(guild_id, user_id) DO UPDATE SET lang=$3',
				ctx.guild.id, 0, language
			)

			await ctx.send(f'Set server-specific highlighting language to \'{language}\'.')

	@commands.command(aliases=['p'], hidden=True)
	async def paste(self, ctx):
		'''Legacy, not removed because some people still use it instead of the newer tags in the tag system.'''

		msg = 'To paste code snippets directly into the chat, use the highlight command:\n```.hl *paste code here*```'
		if ctx.guild.id == AHK_GUILD_ID:
			msg += (
				'If you have a larger script you want to share, paste it to the AutoHotkey pastebin instead:\n'
				'http://p.ahkscript.org/'
			)
		await ctx.send(msg)


def setup(bot):
	bot.add_cog(Highlighter(bot))
