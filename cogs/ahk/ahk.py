import discord
import re

from bs4 import BeautifulSoup
from fuzzywuzzy import process, fuzz
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks

from cogs.ahk.ids import *
from cogs.mixins import AceMixin
from utils.docs_parser import parse_docs
from utils.html2markdown import HTML2Markdown


RSS_URL = 'https://www.autohotkey.com/boards/feed'


class AutoHotkey(AceMixin, commands.Cog):
	'''Commands for the AutoHotkey guild.'''

	DOCS_NO_MATCH = commands.CommandError('Sorry, couldn\'t find an entry similar to that.')

	def __init__(self, bot):
		super().__init__(bot)

		self.h2m = HTML2Markdown(
			escaper=discord.utils.escape_markdown,
			big_box=True, lang='autoit',
			max_len=2000
		)

		self.forum_thread_channel = self.bot.get_channel(FORUM_THRD_CHAN_ID)
		self.forum_reply_channel = self.bot.get_channel(FORUM_REPLY_CHAN_ID)
		self.rss_time = datetime.now(tz=timezone(timedelta(hours=1))) - timedelta(minutes=1)

		self.rss.start()

	def parse_date(self, date_str):
		date_str = date_str.strip()
		return datetime.strptime(date_str[:-3] + date_str[-2:], "%Y-%m-%dT%H:%M:%S%z")

	@tasks.loop(minutes=5)
	async def rss(self):
		async with self.bot.aiohttp.request('get', RSS_URL) as resp:
			if resp.status != 200:
				return
			xml_rss = await resp.text('UTF-8')

		xml = BeautifulSoup(xml_rss, 'xml')

		for entry in xml.find_all('entry')[::-1]:

			time = self.parse_date(str(entry.updated.text))
			title = self.h2m.convert(str(entry.title.text))

			if time > self.rss_time:
				content = str(entry.content.text).split('Statistics: ')[0]
				content = self.h2m.convert(content)

				content = content.replace('CODE:', '')
				content = re.sub('\n\n+', '\n\n', content)

				e = discord.Embed(
					title=title,
					description=content,
					url=str(entry.id.text)
				)

				e.add_field(name='Author', value=str(entry.author.text))
				e.add_field(name='Forum', value=str(entry.category['label']))
				e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')
				e.timestamp = time

				if '• Re: ' in title and self.forum_reply_channel is not None:
					await self.forum_reply_channel.send(embed=e)
				elif self.forum_thread_channel is not None:
					await self.forum_thread_channel.send(embed=e)

				self.rss_time = time

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

		if not matches:
			raise self.DOCS_NO_MATCH

		result = process.extract(
			query,
			[tup.get('name') for tup in matches],
			scorer=fuzz.ratio,
			limit=1
		)

		name, score = result[0]

		if score < 30:
			raise self.DOCS_NO_MATCH

		for match in matches:
			if match[1] == name:
				docs_id = match[0]
				break

		return docs_id, name

	@commands.command(aliases=['rtfm'])
	@commands.bot_has_permissions(embed_links=True)
	async def docs(self, ctx, *, query):
		'''Search the AutoHotkey documentation. Enter multiple queries by separating with commas.'''

		spl = set(st.strip().lower() for st in query.split(','))

		if len(spl) > 3:
			raise commands.CommandError('Maximum three different queries.')
		elif len(spl) > 1:
			for subquery in spl:
				try:
					await ctx.invoke(self.docs, query=subquery)
				except commands.CommandError:
					pass
			return

		docs_id, name = await self.get_docs(spl.pop())

		e = discord.Embed()
		e.color = 0x95CD95

		docs = await self.db.fetchrow('SELECT * FROM docs_entry WHERE id=$1', docs_id)
		syntax = await self.db.fetchrow('SELECT * FROM docs_syntax WHERE docs_id=$1', docs.get('id'))

		page = docs.get('page')
		if page is not None:
			e.url = 'https://autohotkey.com/docs/{}'.format(docs.get('page'))

		e.title = name
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

		try:
			agg = await parse_docs(on_update, download)
		except Exception as exc:
			raise commands.CommandError(str(exc))

		await on_update('Rebuilding database...')

		await self.db.execute('TRUNCATE docs_name, docs_syntax, docs_param, docs_entry RESTART IDENTITY')

		async for entry in agg.get_all():
			names = entry.pop('names')
			page = entry.pop('page')
			desc = entry.pop('desc')
			syntax = entry.pop('syntax', None)

			docs_id = await self.db.fetchval(
				'INSERT INTO docs_entry (page, content) VALUES ($1, $2) RETURNING id',
				page, desc
			)

			for name in names:
				await self.db.execute('INSERT INTO docs_name (docs_id, name) VALUES ($1, $2)', docs_id, name)

			if syntax is not None:
				await self.db.execute('INSERT INTO docs_syntax (docs_id, syntax) VALUES ($1, $2)', docs_id, syntax)

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
