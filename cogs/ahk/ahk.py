import asyncio
import html
import io
import logging
import re
from asyncio import TimeoutError
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from typing import Optional

import disnake
from aiohttp import ClientTimeout
from aiohttp.client_exceptions import ClientConnectorError
from bs4 import BeautifulSoup
from disnake.ext import commands, tasks
from fuzzywuzzy import fuzz, process

from cogs.mixins import AceMixin
from config import CLOUDAHK_PASS, CLOUDAHK_URL, CLOUDAHK_USER
from ids import *
from utils.docs_parser import parse_docs
from utils.html2markdown import HTML2Markdown

log = logging.getLogger(__name__)

AHK_COLOR = 0x95CD95
RSS_URL = 'https://www.autohotkey.com/boards/feed'

DOCS_FORMAT = 'https://autohotkey.com/docs/{}'
DOCS_NO_MATCH = commands.CommandError('Sorry, couldn\'t find an entry similar to that.')

SUGGESTION_PREFIX = 'suggestion:'
UPVOTE_EMOJI = '\N{Thumbs Up Sign}'
DOWNVOTE_EMOJI = '\N{Thumbs Down Sign}'

INACTIVITY_LIMIT = timedelta(weeks=4)

DISCORD_UPLOAD_LIMIT = 8000000  # 8 MB


class RunnableCodeConverter(commands.Converter):
	async def convert(self, ctx, code):
		if code.startswith('https://p.ahkscript.org/'):
			url = code.replace('?p=', '?r=')
			async with ctx.http.get(url) as resp:
				if resp.status == 200 and str(resp.url) == url:
					code = await resp.text()
				else:
					raise commands.CommandError('Failed fetching code from pastebin.')

		return code


class AutoHotkey(AceMixin, commands.Cog):
	'''Commands for the AutoHotkey guild.'''

	def __init__(self, bot):
		super().__init__(bot)

		self._docs_cache = list()

		self.h2m = HTML2Markdown(
			escaper=disnake.utils.escape_markdown,
			big_box=True, lang='autoit',
			max_len=512
		)

		self.h2m_version = HTML2Markdown(
			escaper=disnake.utils.escape_markdown,
			big_box=False, max_len=512
		)

		self.forum_thread_channel = self.bot.get_channel(FORUM_THRD_CHAN_ID)
		self.rss_time = datetime.now(tz=timezone(timedelta(hours=1))) - timedelta(minutes=1)

		self.rss.start()

		asyncio.create_task(self._build_docs_cache())

	def cog_unload(self):
		self.rss.cancel()

	def parse_date(self, date_str):
		date_str = date_str.strip()
		return datetime.strptime(date_str[:-3] + date_str[-2:], "%Y-%m-%dT%H:%M:%S%z")

	async def _build_docs_cache(self):
		records = await self.db.fetch('SELECT name FROM docs_name')
		self._docs_cache = [record.get('name') for record in records]

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

				e = disnake.Embed(
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
	async def handle_emoji_suggestion_message(self, message: disnake.Message):
		if message.guild is None or message.guild.id != AHK_GUILD_ID:
			return

		if message.channel.id != EMOJI_SUGGESTIONS_CHAN_ID:
			return

		if message.author.bot:
			return

		matches = self.find_all_emoji(message)

		async def delete(reason=None):
			if await self.bot.is_owner(message.author):
				return

			try:
				await message.delete()
			except disnake.HTTPException:
				return

			if reason is not None:
				try:
					await message.channel.send(content=f'{message.author.mention} {reason}', delete_after=10)
				except disnake.HTTPException:
					pass

		if not matches and not message.attachments:
			return await delete('Your message has to contain an emoji suggestion.')

		elif message.attachments:
			# if more than one attachment, delete
			if len(message.attachments) > 1:
				return await delete('Please only send one attachment at a time.')

			attachment = message.attachments[0]
			if attachment.height is None:
				return await delete('Your attachment is not an image.')

			if attachment.height != attachment.width:
				return await delete('The attached image is not square.')

			if attachment.size > 256 * 1024:
				return await delete('The attached image is larger than the emoji size limit (256KB).')

			if message.content:
				return await delete('Please do not put text in your suggestion.')

		else:
			if len(matches) > 1:
				return await delete('Please make sure your message only contains only one emoji.')

			if not re.match(r'^<a?:.+?:([0-9]{15,21})>$', message.content.strip()):
				return await delete('Please do not put text alongside your emoji suggestion.')

			match = int(matches[0])
			if any(emoji.id == match for emoji in message.guild.emojis):
				return await delete('Please do not suggest emojis that have already been added.')

		# Add voting reactions
		try:
			await message.add_reaction('✅')
			await message.add_reaction('❌')
		except disnake.Forbidden as e:
			# catch if we can't add the reactions
			# it could be that person is blocked, but it also could be that the bot doesn't have perms
			# we treat it the same since this is only used in the ahk discord.
			if e.text == 'Reaction blocked':
				# runie: don't send error message to user since they have the bot blocked anyways.
				# people who block ace don't deserve answers to their misfortunes
				return await delete()

	@commands.Cog.listener('on_raw_message_edit')
	async def handle_emoji_suggestion_message_edit(self, message: disnake.RawMessageUpdateEvent):
		if message.channel_id == EMOJI_SUGGESTIONS_CHAN_ID:
			channel = self.bot.get_channel(EMOJI_SUGGESTIONS_CHAN_ID)
			if channel is None:
				return

			try:
				await channel.delete_messages([disnake.Object(message.message_id)])
			except disnake.HTTPException:
				pass

	@commands.Cog.listener('on_raw_reaction_add')
	async def handle_emoji_suggestion_reaction(self, reaction: disnake.RawReactionActionEvent):
		if reaction.channel_id != EMOJI_SUGGESTIONS_CHAN_ID:
			return

		if reaction.member.bot:
			return

		emoji = str(reaction.emoji)

		if emoji not in ('✅', '❌'):
			return

		channel: disnake.TextChannel = self.bot.get_channel(reaction.channel_id)
		if channel is None:
			return

		try:
			message: disnake.Message = await channel.fetch_message(reaction.message_id)
		except disnake.HTTPException:
			return

		# remove same emoji if from message author
		if message.author == reaction.member:
			try:
				await message.remove_reaction(emoji, reaction.member)
			except disnake.HTTPException:
				pass
		else:
			# remove opposite emoji if added
			remove_from = '✅' if emoji == '❌' else '❌'

			for reac in message.reactions:
				if str(reac.emoji) == remove_from:
					try:
						users = await reac.users().flatten()
					except disnake.HTTPException:
						return

					if reaction.member in users:
						try:
							await message.remove_reaction(remove_from, reaction.member)
						except disnake.HTTPException:
							pass

					return

	def craft_docs_page(self, record):
		page = record.get('page')

		e = disnake.Embed(
			title=record.get('name'),
			description=record.get('content') or 'No description for this page.',
			color=AHK_COLOR,
			url=None if page is None else DOCS_FORMAT.format(record.get('link'))
		)

		e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')

		syntax = record.get('syntax')
		if syntax is not None:
			e.description += '\n```autoit\n{}\n```'.format(syntax)

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
		'''Call to CloudAHK to run "code" written in "lang". Replies to invoking user with stdout/runtime of code. '''

		token = '{0}:{1}'.format(CLOUDAHK_USER, CLOUDAHK_PASS)

		encoded = b64encode(bytes(token, 'utf-8')).decode('utf-8')
		headers = {'Authorization': 'Basic ' + encoded}

		# remove first line with backticks and highlighting lang
		if re.match('^```.*\n', code):
			code = code[code.find('\n') + 1:]

		# strip backticks on both sides
		code = code.strip('`').strip()

		url = f'{CLOUDAHK_URL}/{lang}/run'

		# call cloudahk with 20 in timeout
		try:
			async with self.bot.aiohttp.post(url, data=code, headers=headers, timeout=ClientTimeout(total=10, connect=5)) as resp:
				if resp.status == 200:
					result = await resp.json()
				else:
					raise commands.CommandError('Something went wrong.')
		except ClientConnectorError:
			raise commands.CommandError('I was unable to connect to the API. Please try again later.')
		except TimeoutError:
			raise commands.CommandError('I timed out. Please try again later.')

		stdout, time = result['stdout'].strip(), result['time']

		file = None
		stdout = stdout.replace('\r', '')

		if time is None:
			resp = 'Program ran for too long and was aborted.'
		else:
			stdout_len = len(stdout)
			display_time = f'Runtime: `{time:.2f}` seconds'

			if stdout_len < 1800 and stdout.count('\n') < 20:
				# upload as plaintext
				stdout = stdout.replace('``', '`\u200b`')

				resp = '```autoit\n{0}\n```{1}'.format(
					stdout if stdout else 'No output.',
					display_time
				)

			elif stdout_len < DISCORD_UPLOAD_LIMIT:
				fp = io.BytesIO(bytes(stdout.encode('utf-8')))
				file = disnake.File(fp, 'output.txt')
				resp = f'Output dumped to file.\n{display_time}'

			else:
				raise commands.CommandError('Output greater than 8 MB.')

		# logging for security purposes and checking for abuse
		filename = 'ahk_eval/{0}_{1}_{2}_{3}'.format(ctx.guild.id, ctx.author.id, ctx.message.id, lang)
		with open(filename, 'w', encoding='utf-8-sig') as f:
			f.write('{0}\n\nLANG: {1}\n\nCODE:\n{2}\n\nPROCESSING TIME: {3}\n\nSTDOUT:\n{4}\n'.format(ctx.stamp, lang, code, time, stdout))

		reference = ctx.message.to_reference()
		reference.fail_if_not_exists = False
		await ctx.send(content=resp, file=file, reference=reference)

	@commands.command()
	@commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
	async def ahk(self, ctx, *, code: RunnableCodeConverter):
		'''Run AHK code through CloudAHK. Example: `ahk print("hello world!")`'''

		await self.cloudahk_call(ctx, code)

	@commands.command(aliases=['d', 'doc', 'rtfm'])
	@commands.bot_has_permissions(embed_links=True)
	async def cmd_docs(self, ctx: commands.Context, *, query: str = None):
		'''Search the AutoHotkey documentation. Enter multiple queries by separating with commas.'''
		if query is None:
			await ctx.send(DOCS_FORMAT.format(''))
			return

		spl = dict.fromkeys(sq.strip() for sq in query.lower().split(','))

		if len(spl) > 3:
			raise commands.CommandError('Maximum three different queries.')

		embeds = []
		for subquery in spl.keys():
			result = await self.get_docs(subquery, count=1, entry=True, syntax=True)
			if not result:
				if len(spl.keys()) == 1:
					raise DOCS_NO_MATCH
				else:
					continue
			embeds.append(self.craft_docs_page(result[0]))

		await ctx.send(embeds=embeds)

	@commands.slash_command(name='docs')
	async def slash_docs(self, inter):
		'''Search autohotkey docs'''
		pass

	@slash_docs.sub_command(name='search')
	async def slash_docs_search(self, inter: disnake.AppCmdInter, query: str) -> None:
		'''
		Search autokey documentation.

		Parameters
		----------
		query: Search query for the documentation
		'''
		result = await self.get_docs(query, count=1, entry=True, syntax=True)

		if not result:
			await inter.response.send_message("Sorry, couldn't find an entry similar to that", ephemeral=True)

		await inter.response.send_message(embed=self.craft_docs_page(result[0]))

	@slash_docs_search.autocomplete('query')
	async def docs_autocomplete(self, inter: disnake.AppCommandInter, query: str):
		res = await self.get_docs(query, count=25, entry=True)
		# this mess is because we want to persist order, remove duplicates,
		# and keep titles to less than 100 characters
		return list(dict.fromkeys([r.get('title')[:100] for r in res], None).keys())

	async def get_docslist(self, query: str) -> Optional[disnake.Embed]:
		results = await self.get_docs(query, count=10, entry=True)

		if not results:
			return None

		entries = []

		for res in results:
			entries.append('[`{}`]({})'.format(res.get('name'), DOCS_FORMAT.format(res.get('link'))))

		return disnake.Embed(
			description='\n'.join(entries),
			color=AHK_COLOR
		)

	@commands.command(aliases=['dl'])
	@commands.bot_has_permissions(embed_links=True)
	async def cmd_docslist(self, ctx, *, query: str):
		'''Find all approximate matches in the AutoHotkey documentation.'''

		embed = await self.get_docslist(query)
		if embed:
			await ctx.send(embed=embed)
		else:
			raise DOCS_NO_MATCH

	@slash_docs.sub_command(name='list')
	async def slash_docs_list(self, inter: disnake.AppCmdInter, query: str):
		'''List several results for a query.'''
		embed = await self.get_docslist(query)
		if embed:
			await inter.response.send_message(embed=embed)
		else:
			raise DOCS_NO_MATCH

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

		await self.db.execute('TRUNCATE docs_name, docs_syntax, docs_entry RESTART IDENTITY')

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

		e = disnake.Embed(
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

		e = disnake.Embed(description=content, color=disnake.Color.green())

		e.set_author(
			name='AutoHotkey_L ' + latest['name'],
			icon_url=latest['author']['avatar_url']
		)

		e.add_field(name='Release page', value=f"[Click here]({latest['html_url']})")
		e.add_field(name='Installer download', value=f"[Click here]({asset['browser_download_url']})")
		e.add_field(name='Downloads', value=asset['download_count'])

		await ctx.send(embed=e)

	@commands.command(hidden=True)
	@commands.cooldown(rate=1, per=5.0, type=commands.BucketType.user)
	async def rlx(self, ctx, *, code: RunnableCodeConverter):
		'''Compile and run Relax code through CloudAHK. Example: `rlx define i32 Main() {return 20}`'''

		await self.cloudahk_call(ctx, code, 'rlx')


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
