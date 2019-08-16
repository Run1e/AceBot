import discord
import logging

from fuzzywuzzy import process, fuzz
from discord.ext import commands, tasks

from cogs.ahk.ids import AHK_GUILD_ID
from cogs.mixins import AceMixin
from utils.docs_parser import parse_docs
from utils.html2markdown import html2markdown


class AutoHotkey(AceMixin, commands.Cog):
	'''Commands for the AutoHotkey guild.'''

	def __init__(self, bot):
		super().__init__(bot)

		# start rss

	@commands.Cog.listener()
	async def on_command_error(self, ctx, error):
		if not hasattr(ctx, 'guild') or ctx.guild.id not in (AHK_GUILD_ID, 517692823621861407):
			return

		if not await self.bot.blacklist(ctx):
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			try:
				await ctx.invoke(self.docs, query=ctx.message.content[1:])
				ctx.command = self.docs
				await self.bot.on_command_completion(ctx)
			except commands.CommandError as exc:
				await self.bot.on_command_error(ctx=ctx, exc=exc)

	async def get_docs(self, query):
		query = query.lower()

		match = await self.db.fetchrow('SELECT docs_id, name FROM docs_name WHERE LOWER(name)=$1', query)

		if match is not None:
			return match.get('docs_id'), match.get('name')

		# get five results from docs_name
		matches = await self.db.fetch(
			"SELECT docs_id, name FROM docs_name ORDER BY word_similarity($1, name) DESC LIMIT 8",
			query
		)

		result = process.extract(
			query,
			[tup.get('name') for tup in matches],
			scorer=fuzz.ratio,
			limit=1
		)

		name, score = result[0]

		if score < 30:
			raise commands.CommandError('Sorry, couldn\'t find an entry similar to that.')

		for match in matches:
			if match[1] == name:
				docs_id = match[0]
				break

		return docs_id, name

	@commands.command(aliases=['rtfm'])
	@commands.bot_has_permissions(embed_links=True)
	async def docs(self, ctx, *, query):
		'''Search the AutoHotkey documentation. Enter multiple queries by separating with commas.'''

		spl = set(query.split(','))

		if len(spl) > 3:
			raise commands.CommandError('Maximum three different queries.')
		elif len(spl) > 1:
			for query in spl:
				query = query.strip()
				try:
					await ctx.invoke(self.docs, query=query)
				except commands.CommandError:
					pass
			return

		docs_id, name = await self.get_docs(query)

		e = discord.Embed()
		e.color = 0x95CD95

		docs = await self.db.fetchrow('SELECT * FROM docs_entry WHERE id=$1', docs_id)
		syntax = await self.db.fetchrow('SELECT * FROM docs_syntax WHERE docs_id=$1', docs.get('id'))

		e.title = name
		e.url = 'https://autohotkey.com/docs/{}'.format(docs.get('page'))
		e.description = docs.get('content') or 'No description for this page.'
		e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')

		if syntax is not None:
			e.description += '\n```autoit\n{}```'.format(syntax.get('syntax'))

		await ctx.send(embed=e)

	@commands.command(hidden=True)
	@commands.is_owner()
	async def build(self, ctx, download: bool = True):
		async def on_update(text):
			await ctx.send(text)

		async def handler(names, page, desc=None, syntax=None, params=None):

			# ignore everything that has to do with examples
			for name in names:
				if 'example' in name.lower():
					return

			docs_id = await self.db.fetchval('SELECT id FROM docs_entry WHERE page=$1', page)

			if docs_id is None:
				docs_id = await self.db.fetchval(
					'INSERT INTO docs_entry (page, content) VALUES ($1, $2) RETURNING id',
					page, desc
				)

			for name in names:
				# don't add if item already exists (including case insensitive matches)
				if await self.db.fetchval('SELECT id FROM docs_name WHERE LOWER(name)=$1', name.lower()):
					continue
				if name.endswith('()') and await self.db.fetchval('SELECT id FROM docs_name WHERE LOWER(name)=$1', name.lower()[:-2]):
					continue
				await self.db.execute('INSERT INTO docs_name (docs_id, name) VALUES ($1, $2)', docs_id, name)

			if syntax is not None:
				await self.db.execute('INSERT INTO docs_syntax (docs_id, syntax) VALUES ($1, $2)', docs_id, syntax)

			if params is not None:
				for name, value in params.items():
					await self.db.execute(
						'INSERT INTO docs_param (docs_id, name, value) VALUES ($1, $2, $3)',
						docs_id, name, value
					)

		await self.db.execute('TRUNCATE docs_name, docs_syntax, docs_param, docs_entry RESTART IDENTITY')

		try:
			await parse_docs(handler, on_update, download)
		except Exception as exc:
			raise commands.CommandError(str(exc))

	@commands.command()
	async def version(self, ctx):
		'''Get changelog and download for the latest AutoHotkey_L version.'''

		url = 'https://api.github.com/repos/Lexikos/AutoHotkey_L/releases'

		async with self.bot.aiohttp.request('get', url) as resp:
			if resp.status != 200:
				raise commands.CommandError('Query failed.')

			js = await resp.json()

		latest = js[0]
		asset = latest['assets'][0]

		e = discord.Embed(
			description='Update notes:\n```\n' + latest['body'] + '\n```'
		)

		e.set_author(
			name='AutoHotkey_L ' + latest['name'],
			icon_url=latest['author']['avatar_url']
		)

		e.add_field(name='Release page', value=f"[Click here]({latest['html_url']})")
		e.add_field(name='Installer download', value=f"[Click here]({asset['browser_download_url']})")
		e.add_field(name='Downloads', value=asset['download_count'])

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
