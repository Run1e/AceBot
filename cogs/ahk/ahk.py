import html
import logging
import re
import io
from base64 import b64encode
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

import discord
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
from fuzzywuzzy import fuzz, process

from ids import *
from cogs.mixins import AceMixin
from config import CLOUDAHK_PASS, CLOUDAHK_URL, CLOUDAHK_USER
from utils.docs_parser import parse_docs
from utils.html2markdown import HTML2Markdown
from utils.pager import Pager
from utils.string import po
from utils.time import pretty_timedelta

log = logging.getLogger(__name__)

AHK_COLOR = 0x95CD95
RSS_URL = 'https://www.autohotkey.com/boards/feed'

DOCS_FORMAT = 'https://autohotkey.com/docs/{}'
DOCS_NO_MATCH = commands.CommandError('Sorry, couldn\'t find an entry similar to that.')

SUGGESTION_PREFIX = 'suggestion:'
UPVOTE_EMOJI = '\N{Thumbs Up Sign}'
DOWNVOTE_EMOJI = '\N{Thumbs Down Sign}'

INACTIVITY_LIMIT = timedelta(weeks=4)


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

	@tasks.loop(minutes=14)
	async def rss(self):
		async with self.bot.aiohttp.request('get', RSS_URL) as resp:
			if resp.status != 200:
				return
			xml_rss = await resp.text('UTF-8')

		xml = BeautifulSoup(xml_rss, 'xml')

		for entry in reversed(xml.find_all('entry')):

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

	def find_all_emoji(self, message, *, regex=re.compile(r'<a?:.+?:([0-9]{15,21})>')):
		return regex.findall(message.content)

	@commands.Cog.listener('on_message')
	async def handle_emoji_suggestion_message(self, message: discord.Message):
		if message.guild is None or message.guild.id != AHK_GUILD_ID:
			return

		if message.channel.id != EMOJI_SUGGESTIONS_CHAN_ID:
			return

		if message.author.bot:
			return

		matches = self.find_all_emoji(message)

		async def delete():
			if not await self.bot.is_owner(message.author):
				try:
					await message.delete()
				except discord.HTTPException:
					pass

		if not matches and not message.attachments:
			return await delete()
		elif message.attachments:
			# if more than one attachment, delete
			if len(message.attachments) > 1:
				return await delete()
			# if attachment is not an image, delete
			if message.attachments[0].height is None:
				return await delete()
			if message.content:
				return await delete()
		elif len(matches) > 1:
			# if no attachments, make sure there's not multiple emojis
			return await delete()

		# Add voting reactions
		await message.add_reaction('✅')
		await message.add_reaction('❌')

	@commands.Cog.listener('on_raw_message_edit')
	async def handle_emoji_suggestion_message_edit(self, message: discord.RawMessageUpdateEvent):
		if message.channel_id == EMOJI_SUGGESTIONS_CHAN_ID:
			channel = self.bot.get_channel(EMOJI_SUGGESTIONS_CHAN_ID)
			if channel is None:
				return

			try:
				await channel.delete_messages([discord.Object(message.message_id)])
			except discord.HTTPException:
				pass

	@commands.Cog.listener('on_raw_reaction_add')
	async def handle_emoji_suggestion_reaction(self, reaction: discord.RawReactionActionEvent):
		if reaction.channel_id != EMOJI_SUGGESTIONS_CHAN_ID:
			return

		if reaction.member.bot:
			return

		emoji = str(reaction.emoji)

		if emoji not in ('✅', '❌'):
			return

		channel: discord.TextChannel = self.bot.get_channel(reaction.channel_id)
		if channel is None:
			return

		try:
			message: discord.Message = await channel.fetch_message(reaction.message_id)
		except discord.HTTPException:
			return

		# remove same emoji if from message author
		if message.author == reaction.member:
			try:
				await message.remove_reaction(emoji, reaction.member)
			except discord.HTTPException:
				pass
		else:
			# remove opposite emoji if added
			remove_from = '✅' if emoji == '❌' else '❌'

			for reac in message.reactions:
				if str(reac.emoji) == remove_from:
					try:
						users = await reac.users().flatten()
					except discord.HTTPException:
						return

					if reaction.member in users:
						try:
							await message.remove_reaction(remove_from, reaction.member)
						except discord.HTTPException:
							pass

					return

	def craft_docs_page(self, record):
		page = record.get('page')

		e = discord.Embed(
			title=record.get('name'),
			description=record.get('content') or 'No description for this page.',
			color=AHK_COLOR,
			url=None if page is None else DOCS_FORMAT.format(record.get('link'))
		)

		# e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')

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

	async def cloudahk_call(self, ctx, code, lang='ahk'):
		'''Call to CloudAHK to run %code% written in %lang%. Replies to invoking user with stdout/runtime of code. '''

		token = '{0}:{1}'.format(CLOUDAHK_USER, CLOUDAHK_PASS)

		encoded = b64encode(bytes(token, 'utf-8')).decode('utf-8')
		headers = {'Authorization': 'Basic ' + encoded}

		# remove first line with backticks and highlighting lang
		if re.match('^```.*\n', code):
			code = code[code.find('\n') + 1:]

		# strip backticks on both sides
		code = code.strip('`').strip()

		# call cloudahk with 20 in timeout
		async with self.bot.aiohttp.post('{}/{}/run'.format(CLOUDAHK_URL, lang), data=code, headers=headers, timeout=20) as resp:
			if resp.status == 200:
				result = await resp.json()
			else:
				raise commands.CommandError('Something went wrong.')

		stdout, time = result['stdout'].strip(), result['time']

		stdout = stdout.replace('`', '`\u200b')
		file = None
		encoded_stdout = stdout.encode('utf-8')

		if len(stdout) < 1800 and stdout.count('\n') < 20 and stdout.count('\r') < 20:
			#upload as plaintext
			valid_response = '` No Output.\n`' if stdout == '' else '\n```autoit\n{0}\n```'.format(stdout)
		

		elif len(stdout) < (8000000000): # limited to 8mb
			fp = io.BytesIO(encoded_stdout)
			file = discord.File(fp, 'results.txt')
			valid_response = ' Results too large. See attached file.\n'
			
		else:
			raise commands.CommandError('Output greater than 8mb.')

		out = '{}{}{}'.format(
			ctx.author.mention,
			valid_response,
			'`Processing time: {}`'.format('Timed out' if time is None else '{0:.1f} seconds'.format(time))
		)
		

		try:
			await ctx.reply(content=out, file=file)
		except discord.HTTPException:
			await ctx.send(content=out, file=file)

		return stdout, time

	@commands.command()
	@commands.cooldown(rate=1.0, per=5.0, type=commands.BucketType.user)
	async def ahk(self, ctx, *, code):
		'''Run AHK code through CloudAHK. Example: `ahk print("hello world!")`'''
		
		if code.startswith('https://p.ahkscript.org/'):
			url = code.replace('?p=','?r=')
			async with ctx.http.get(url) as resp:
				if resp.status == 200 and str(resp.url) == url:
					code = await resp.text()
				else:
					raise commands.CommandError('Invalid link or the server did not respond.')


		stdout, time = await self.cloudahk_call(ctx, code)

		# logging for security purposes and checking for abuse
		with open('ahk_eval/{0}_{1}_{2}'.format(ctx.guild.id, ctx.author.id, ctx.message.id), 'w', encoding='utf-8-sig') as f:
			f.write('{0}\n\nCODE:\n{1}\n\nPROCESSING TIME: {2}\n\nSTDOUT:\n{3}\n'.format(ctx.stamp, code, time, stdout))

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
		log.info('Starting documentation build job. Download=%s', download)

		async def on_update(text):
			log.info('Build job: %s', text)
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
			'search': query,
			'$top': 1,
		}

		async with ctx.http.get(url, params=params) as resp:
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
			description=description,
			color=AHK_COLOR,
			url=result['url']
		)

		e.set_footer(text='docs.microsoft.com', icon_url='https://i.imgur.com/UvkNAEh.png')

		await ctx.send(embed=e)

	@commands.command()
	async def version(self, ctx):
		'''Get changelog and download for the latest AutoHotkey_L version.'''

		url = 'https://api.github.com/repos/Lexikos/AutoHotkey_L/releases'

		async with ctx.http.get(url) as resp:
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

	@commands.command(hidden=True)
	@commands.cooldown(rate=1.0, per=5.0, type=commands.BucketType.user)
	async def rlx(self, ctx, *, code):
		'''Compile and run Relax code through CloudAHK. Example: `rlx define i32 Main() {return 20}`'''

		await self.cloudahk_call(ctx, code, 'rlx')


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
