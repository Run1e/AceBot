import discord
import re
import html

from bs4 import BeautifulSoup
from fuzzywuzzy import process, fuzz
from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks

from cogs.ahk.ids import *
from cogs.mixins import AceMixin
from utils.pager import Pager
from utils.docs_parser import parse_docs
from utils.html2markdown import HTML2Markdown


RSS_URL = 'https://www.autohotkey.com/boards/feed'
DOCS_FORMAT = 'https://autohotkey.com/docs/{}'
DOCS_NO_MATCH = commands.CommandError('Sorry, couldn\'t find an entry similar to that.')


class DocsPagePager(Pager):
	async def craft_page(self, e, page, entries):
		e.title = self.header.get('page')
		e.url = DOCS_FORMAT.format(self.header.get('link'))
		e.color = 0x95CD95

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

				content = content.replace('CODE: ', '')
				content = re.sub('\n\n+', '\n\n', content)
				content = re.sub('\n```\n+', '\n```\n', content)

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

		# command not found? docs search it. only if message string is not *only* dots though
		if type(error) is commands.CommandNotFound and len(ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			if not await self.bot.blacklist(ctx):
				return

			await ctx.send('If you meant to bring up the docs, please do `.d <query>` instead.')

	async def get_docs(self, query, count=1):
		query = query.lower()

		results = list()
		already_added = set()

		match = await self.db.fetchrow('SELECT * FROM docs_name WHERE LOWER(name)=$1', query)

		if match is not None:
			results.append(match)

			already_added.add(match.get('id'))

			if count == 1:
				return results

		# get five results from docs_name
		matches = await self.db.fetch(
			'SELECT * FROM docs_name ORDER BY word_similarity($1, name) DESC LIMIT 8', query
		)

		if not matches:
			return results

		fuzzed = process.extract(
			query=query,
			choices=[tup.get('name') for tup in matches],
			scorer=fuzz.ratio,
			limit=count - len(results)
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

		spl = dict.fromkeys(st.strip() for st in query.lower().split(','))

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

		result = await self.get_docs(query, count=1)

		if not result:
			raise DOCS_NO_MATCH

		docs_id, name = result[0].get('docs_id'), result[0].get('name')

		docs = await self.db.fetchrow('SELECT * FROM docs_entry WHERE id=$1', docs_id)
		syntax = await self.db.fetchrow('SELECT * FROM docs_syntax WHERE docs_id=$1', docs.get('id'))

		page = docs.get('page')

		e = discord.Embed(
			title=name,
			description=docs.get('content') or 'No description for this page.',
			color=0x95CD95,
			url=None if page is None else DOCS_FORMAT.format(docs.get('link'))
		)

		e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')

		if syntax is not None:
			e.description += '\n```autoit\n{}```'.format(syntax.get('syntax'))

		await ctx.send(embed=e)

	@commands.command(aliases=['dl'])
	@commands.bot_has_permissions(embed_links=True)
	async def docslist(self, ctx, *, query):
		'''Find all approximate matches in the AutoHotkey documentation.'''

		results = await self.get_docs(query, count=10)

		if not results:
			raise DOCS_NO_MATCH

		entries = list()

		for res in results:
			link = await self.db.fetchval('SELECT link FROM docs_entry WHERE id=$1', res.get('docs_id'))
			entries.append('[`{}`]({})'.format(res.get('name'), DOCS_FORMAT.format(link)))

		e = discord.Embed(
			description='\n'.join(entries),
			color=0x95CD95
		)

		await ctx.send(embed=e)

	@commands.command(aliases=['dp'])
	@commands.bot_has_permissions(embed_links=True)
	async def docspage(self, ctx, *, query):
		'''List entries of an AutoHotkey documentation page.'''

		query = query.lower()

		entry = await self.get_docs(query, count=1)

		if not entry:
			raise DOCS_NO_MATCH

		entry = entry[0]

		subheader = await self.db.fetchrow('SELECT * FROM docs_entry WHERE id=$1', entry.get('docs_id'))

		if subheader.get('fragment') is None:
			header = subheader
		else:
			header = await self.db.fetchrow(
				'SELECT * FROM docs_entry WHERE page=$1 AND fragment IS NULL', subheader.get('page')
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

		e = discord.Embed(
			title=html.unescape(result['title']),
			description=html.unescape(result['description']),
			color=0x95CD95,
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
