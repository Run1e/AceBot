import discord
import html

from discord.ext import commands, tasks
from collections import OrderedDict
from bs4 import BeautifulSoup
from fuzzywuzzy import process, fuzz
from datetime import datetime, timedelta, timezone

from cogs.ahk.ids import *
from cogs.mixins import AceMixin
from utils.pager import Pager
from utils.docs_parser import parse_docs
from utils.html2markdown import HTML2Markdown


AHK_COLOR = 0x95CD95
RSS_URL = 'https://www.autohotkey.com/boards/feed'
DOCS_FORMAT = 'https://autohotkey.com/docs/{}'
DOCS_NO_MATCH = commands.CommandError('Sorry, couldn\'t find an entry similar to that.')


class DocsPagePager(Pager):
	async def craft_page(self, e, page, entries):
		e.title = self.header.get('page')
		e.url = DOCS_FORMAT.format(self.header.get('link'))
		e.color = AHK_COLOR

		e.description = '\n'.join(
			'[`{}`]({})'.format(
				entry.get('title'),
				DOCS_FORMAT.format(entry.get('link'))
			) for entry in entries
		)


class AutoHotkey(AceMixin, commands.Cog):
	'''Commands for the AutoHotkey guild.'''

	def __init__(self, bot):
		super().__init__(bot)

		self.h2m = HTML2Markdown(
			escaper=discord.utils.escape_markdown,
			big_box=True, lang='autoit',
			max_len=512
		)

		self.h2m_version = HTML2Markdown(
			escaper=discord.utils.escape_markdown,
			big_box=False, max_len=512
		)

		self.forum_thread_channel = self.bot.get_channel(FORUM_THRD_CHAN_ID)
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

			if time > self.rss_time and '• Re: ' not in title:
				content = str(entry.content.text).split('Statistics: ')[0]
				content = self.h2m.convert(content)
				content = content.replace('\nCODE: ', '')

				e = discord.Embed(
					title=title,
					description=content,
					url=str(entry.id.text),
					color=AHK_COLOR
				)

				e.add_field(name='Author', value=str(entry.author.text))
				e.add_field(name='Forum', value=str(entry.category['label']))
				e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')
				e.timestamp = time

				if self.forum_thread_channel is not None:
					await self.forum_thread_channel.send(embed=e)

			self.rss_time = time

	def craft_docs_page(self, record):
		page = record.get('page')

		e = discord.Embed(
			title=record.get('name'),
			description=record.get('content') or 'No description for this page.',
			color=AHK_COLOR,
			url=None if page is None else DOCS_FORMAT.format(record.get('link'))
		)

		e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')

		syntax = record.get('syntax')
		if syntax is not None:
			e.description += '\n```autoit\n{}```'.format(syntax)

		return e

	async def get_docs(self, query, count=1, entry=False, syntax=False):
		query = query.lower()

		results = list()
		already_added = set()

		sql = 'SELECT * FROM docs_name '

		if entry:
			sql += 'INNER JOIN docs_entry ON docs_name.docs_id = docs_entry.id '

		if syntax:
			sql += 'LEFT OUTER JOIN docs_syntax ON docs_name.docs_id = docs_syntax.docs_id '

		sql += 'ORDER BY word_similarity(name, $1) DESC, LOWER(name)=$1 DESC LIMIT $2'

		# get 8 closes matches according to trigram matching
		matches = await self.db.fetch(sql, query, max(count, 8))

		if not matches:
			return results

		# further fuzzy search it using fuzzywuzzy ratio matching
		fuzzed = process.extract(
			query=query,
			choices=[tup.get('name') for tup in matches],
			scorer=fuzz.ratio,
			limit=count
		)

		if not fuzzed:
			return results

		for res in fuzzed:
			for match in matches:
				if res[0] == match.get('name') and match.get('id') not in already_added:
					results.append(match)
					already_added.add(match.get('id'))

		return results

	@commands.command(aliases=['d', 'doc', 'rtfm'])
	@commands.bot_has_permissions(embed_links=True)
	async def docs(self, ctx, *, query):
		'''Search the AutoHotkey documentation. Enter multiple queries by separating with commas.'''

		spl = OrderedDict.fromkeys(sq.strip() for sq in query.lower().split(','))

		if len(spl) > 3:
			raise commands.CommandError('Maximum three different queries.')

		if len(spl) > 1:
			for subquery in spl.keys():
				try:
					await ctx.invoke(self.docs, query=subquery)
				except commands.CommandError:
					pass

			return

		query = spl.popitem()[0]

		result = await self.get_docs(query, count=1, entry=True, syntax=True)

		if not result:
			raise DOCS_NO_MATCH

		await ctx.send(embed=self.craft_docs_page(result[0]))

	@commands.command(aliases=['dl'])
	@commands.bot_has_permissions(embed_links=True)
	async def docslist(self, ctx, *, query):
		'''Find all approximate matches in the AutoHotkey documentation.'''

		results = await self.get_docs(query, count=10, entry=True)

		if not results:
			raise DOCS_NO_MATCH

		entries = list()

		for res in results:
			entries.append('[`{}`]({})'.format(res.get('name'), DOCS_FORMAT.format(res.get('link'))))

		e = discord.Embed(
			description='\n'.join(entries),
			color=AHK_COLOR
		)

		await ctx.send(embed=e)

	@commands.command(aliases=['dp'])
	@commands.bot_has_permissions(embed_links=True)
	async def docspage(self, ctx, *, query):
		'''List entries of an AutoHotkey documentation page.'''

		query = query.lower()

		entry = await self.get_docs(query, count=1, entry=True)

		if not entry:
			raise DOCS_NO_MATCH

		entry = entry[0]

		if entry.get('fragment') is None:
			header = entry
		else:
			header = await self.db.fetchrow(
				'SELECT * FROM docs_entry WHERE page=$1 AND fragment IS NULL', entry.get('page')
			)

			if header is None:
				raise commands.CommandError('Header for this entry not found.')

		records = await self.db.fetch(
			'SELECT * FROM docs_entry WHERE page=$1 AND fragment IS NOT NULL ORDER BY id', header.get('page')
		)

		if not records:
			raise commands.CommandError('Page has no fragments.')

		p = DocsPagePager(ctx, entries=records, per_page=16)
		p.header = header

		await p.go()

	@commands.command(hidden=True)
	@commands.is_owner()
	async def build(self, ctx, download: bool = True):
		async def on_update(text):
			await ctx.send(text)

		try:
			agg = await parse_docs(on_update, fetch=download, loop=ctx.bot.loop)
		except Exception as exc:
			raise commands.CommandError(str(exc))

		await on_update('Building tables...')

		await self.db.execute('TRUNCATE docs_name, docs_syntax, docs_param, docs_entry RESTART IDENTITY')

		async for entry in agg:
			names = entry.pop('names')
			link = entry.pop('page')
			desc = entry.pop('desc')
			syntax = entry.pop('syntax', None)

			if link is None:
				page = None
				fragment = None
			else:
				split = link.split('/')
				split = split[len(split) - 1].split('#')
				page = split.pop(0)[:-4]
				fragment = split.pop(0) if split else None

			docs_id = await self.db.fetchval(
				'INSERT INTO docs_entry (content, link, page, fragment, title) VALUES ($1, $2, $3, $4, $5) '
				'RETURNING id',
				desc, link, page, fragment, entry['main']
			)

			for name in names:
				await self.db.execute('INSERT INTO docs_name (docs_id, name) VALUES ($1, $2)', docs_id, name)

			if syntax is not None:
				await self.db.execute('INSERT INTO docs_syntax (docs_id, syntax) VALUES ($1, $2)', docs_id, syntax)

		await on_update('Done!')

	@commands.command()
	async def msdn(self, ctx, *, query):
		'''Search the Microsoft documentation.'''

		url = 'https://docs.microsoft.com/api/search'

		params = {
			'filter': "category eq 'Documentation'",
			'locale': 'en-us',
			'scoringprofile': 'search_for_en_us_pageview',
			'search': query,
			'$top': 1,
		}

		async with self.bot.aiohttp.get(url, params=params) as resp:
			if resp.status != 200:
				raise commands.CommandError('Query failed.')

			json = await resp.json()

		if 'results' not in json or not json['results']:
			raise commands.CommandError('No results.')

		result = json['results'][0]

		if result['description'] is None:
			description = 'No description for this page.'
		else:
			description = html.unescape(result['description'])

		e = discord.Embed(
			title=html.unescape(result['title']),
			description= description,
			color=AHK_COLOR,
			url=result['url']
		)

		e.set_footer(text='docs.microsoft.com', icon_url='https://i.imgur.com/UvkNAEh.png')

		await ctx.send(embed=e)

	@commands.command()
	async def version(self, ctx):
		'''Get changelog and download for the latest AutoHotkey_L version.'''

		url = 'https://api.github.com/repos/Lexikos/AutoHotkey_L/releases'

		async with self.bot.aiohttp.get(url) as resp:
			if resp.status != 200:
				raise commands.CommandError('Query failed.')

			js = await resp.json()

		latest = js[0]
		asset = latest['assets'][0]

		content = self.h2m_version.convert(latest['body'])

		e = discord.Embed(description=content, color=discord.Color.green())

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
