import asyncio
import copy
import io
import logging
import textwrap
import traceback
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from urllib.parse import urlparse

import discord
from bs4 import BeautifulSoup
from discord.ext import commands
from discord.mixins import Hashable
from tabulate import tabulate

from cogs.mixins import AceMixin
from config import BOT_ACTIVITY
from utils.context import AceContext
from utils.converters import MaxValueConverter
from utils.lookup import DiscordLookup
from utils.pager import Pager
from utils.string import shorten
from utils.time import pretty_datetime, pretty_timedelta

log = logging.getLogger(__name__)


class DiscordObjectPager(Pager):
	async def craft_page(self, e, page, entries):
		entry = entries[0]

		e.description = ''

		for field in dir(entry):
			if field.startswith('_'):
				continue

			try:
				attr = getattr(entry, field)
			except AttributeError:
				continue

			if callable(attr):
				continue

			if isinstance(attr, int):
				e.add_field(name=field, value='`{}`'.format(str(attr)), inline=False)

			elif isinstance(attr, str):
				e.add_field(name=field, value=attr, inline=False)

			elif isinstance(attr, datetime):
				e.add_field(name=field, value=pretty_datetime(attr), inline=False)

			elif isinstance(attr, list) and len(attr) and field not in ('members',):
				lst = list()
				for item in attr:
					if hasattr(item, 'mention'):
						lst.append(item.mention)
					elif hasattr(item, 'name'):
						lst.append(item.name)
					elif hasattr(item, 'id'):
						lst.append(item.id)

				if len(lst):
					e.add_field(name=field, value=shorten(' '.join(lst), 1024), inline=False)

		if hasattr(entry, 'name'):
			e.title = entry.name

		if hasattr(entry, 'mention'):
			e.description = entry.mention

		if hasattr(entry, 'avatar_url'):
			e.set_thumbnail(url=entry.avatar_url)
		elif hasattr(entry, 'icon_url'):
			e.set_thumbnail(url=entry.icon_url)


class Owner(AceMixin, commands.Cog):
	'''Commands accessible only to the bot owner.'''

	DISCORD_BASE_TYPES = (
		discord.Object, discord.Emoji, discord.abc.Messageable, discord.mixins.Hashable
	)

	def __init__(self, bot):
		super().__init__(bot)

		self.help_cog = bot.get_cog('AutoHotkeyHelpSystem')
		self.event_counter = Counter()

	async def cog_check(self, ctx):
		return await self.bot.is_owner(ctx.author)

	def cleanup_code(self, content):
		'''Automatically removes code blocks from the code.'''

		# remove ```py\n```
		if content.startswith('```') and content.endswith('```'):
			return '\n'.join(content.split('\n')[1:-1])

		# remove `foo`
		return content.strip('` \n')

	@commands.Cog.listener()
	async def on_socket_response(self, msg):
		t = msg['t']

		if t is not None:
			self.event_counter[t] += 1

	@commands.command(hidden=True)
	async def c(self, ctx, *, text):
		await ctx.send(self.help_cog.classify(text))

	@commands.command(hidden=True)
	async def cm(self, ctx, *, message: discord.Message):
		await ctx.send(self.help_cog.classify(message.content))

	@commands.command()
	async def t(self, ctx):
		s = (
			'Your scripting question looks like it might be about a game, which is not allowed here. '
			'Please make sure you are familiar with the #rules, specifically rule 5.\n\n'
			'If your question is not about cheating in or automating a game, please disregard this message.'
		)

		e = discord.Embed(
			description=s
		)

		await ctx.send(content=ctx.author.mention, embed=e)

	@commands.command()
	async def eval(self, ctx, *, body: str):
		'''Evaluates some code.'''

		from pprint import pprint
		from tabulate import tabulate

		env = {
			'discord': discord,
			'bot': self.bot,
			'ctx': ctx,
			'channel': ctx.channel,
			'author': ctx.author,
			'guild': ctx.guild,
			'message': ctx.message,
			'pprint': pprint,
			'tabulate': tabulate,
			'db': self.db
		}

		env.update(globals())

		body = self.cleanup_code(body)
		stdout = io.StringIO()

		to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

		try:
			exec(to_compile, env)
		except Exception as e:
			return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

		func = env['func']
		try:
			with redirect_stdout(stdout):
				ret = await func()
		except Exception as e:
			value = stdout.getvalue()
			await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
		else:
			value = stdout.getvalue()
			try:
				await ctx.message.add_reaction('\u2705')
			except:
				pass

			if ret is None:
				if value:
					if len(value) > 1990:
						fp = io.BytesIO(value.encode('utf-8'))
						await ctx.send('Log too large...', file=discord.File(fp, 'results.txt'))
					else:
						await ctx.send(f'```py\n{value}\n```')

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def get(self, ctx, *, query: commands.clean_content):
		'''Run a meta-python query.'''

		try:
			res = DiscordLookup(ctx, query).run()
		except Exception as exc:
			raise commands.CommandError('{}\n\n{}'.format(exc.__class__.__name__, str(exc)))

		if res is None or (isinstance(res, list) and not res):
			raise commands.CommandError('No results.')

		if not isinstance(res, list):
			res = [res]

		if isinstance(res[0], self.DISCORD_BASE_TYPES):
			p = DiscordObjectPager(ctx, entries=res, per_page=1)
			await p.go()
		else:
			res = '\n'.join('`{}`'.format(str(item)) if isinstance(item, int) else str(item) for item in res)

			if len(res) > 2000:
				fp = io.BytesIO(str(res).encode('utf-8'))
				await ctx.send('Log too large...', file=discord.File(fp, 'results.txt'))
			else:
				await ctx.send(embed=discord.Embed(description=res))

	@commands.command()
	async def sql(self, ctx, *, query: str):
		'''Execute a SQL query.'''

		try:
			result = await self.db.fetch(query)
		except Exception as exc:
			raise commands.CommandError(str(exc))

		if not len(result):
			await ctx.send('No rows returned.')
			return

		table = tabulate(result, result[0].keys())

		if len(table) > 1994:
			fp = io.BytesIO(table.encode('utf-8'))
			await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
		else:
			await ctx.send('```' + table + '```')

	@commands.command()
	async def gateway(self, ctx, *, n=None):
		'''Print gateway event counters.'''

		data = self.event_counter.most_common(n)
		data = [(name, format(count, ',d')) for name, count in data]
		headers = ('Event', 'Count')

		await ctx.send('```{0}```'.format(tabulate(data, headers)))

	@commands.command()
	async def test(self, ctx):
		raise ValueError('test')

	@commands.command()
	async def level(self, ctx, *, level):
		'''Change the logging level for debugging purposes.'''

		lvl = getattr(logging, level.upper())
		logging.getLogger().setLevel(lvl)
		await ctx.send('Logging level is {0}'.format(lvl))

	@commands.command()
	async def ping(self, ctx):
		'''Check response time.'''

		msg = await ctx.send('Wait...')

		await msg.edit(content='Response: {}.\nGateway: {}'.format(
			pretty_timedelta(msg.created_at - ctx.message.created_at),
			pretty_timedelta(timedelta(seconds=self.bot.latency))
		))

	@commands.command()
	async def repeat(self, ctx, repeats: int, *, command):
		'''Repeat a command.'''

		if repeats < 1:
			raise commands.CommandError('Repeat count must be more than 0.')

		msg = copy.copy(ctx.message)
		msg.content = ctx.prefix + command

		new_ctx = await self.bot.get_context(msg, cls=AceContext)

		for i in range(repeats):
			await new_ctx.reinvoke()

	@commands.command(name='reload', aliases=['rl'])
	@commands.bot_has_permissions(add_reactions=True)
	async def _reload(self, ctx):
		'''Reload edited extensions.'''

		reloaded, errored = self.bot.load_extensions(reload=True)
		out = ''
		if reloaded or errored:
			if reloaded:
				log.info('Reloaded cogs: %s', ', '.join(reloaded))
				out += 'Reloaded cogs: ' + ', '.join('`{0}`'.format(ext) for ext in reloaded)
			if errored:
				# some cogs failed to reload
				out += '\n\nThese cogs errored:```diff\n'

				for e in errored:
					log.error(f'{e[0]} failed to reload: {e[1]}')
					out += f'- {e[0]}: {e[1]}'
				out += '\n```'
				out = out.strip('\n')
		else:
			await ctx.send('Nothing to reload.')

		await ctx.send(out)

	@commands.command()
	async def decache(self, ctx, guild_id: int):
		'''Clear cache of table data of a specific guild.'''

		configs = (
			self.bot.config,
			self.bot.get_cog('Starboard').config,
			self.bot.get_cog('Moderation').config,
			self.bot.get_cog('Welcome').config,
			self.bot.get_cog('Roles').config,
		)

		cleared = []

		for config in configs:
			if await config.clear_entry(guild_id):
				cleared.append(config)

		await ctx.send('Cleared entries for:\n```\n{0}\n```'.format('\n'.join(config.table for config in cleared)))

	@commands.command(aliases=['g'])
	@commands.bot_has_permissions(embed_links=True)
	async def google(self, ctx, *, query: str):
		'''Get first result from google.'''

		headers = {
			'User-Agent': (
				'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
				'Chrome/39.0.2171.95 Safari/537.36'
			),
			'Accept:': 'text/html'
		}

		params = dict(
			hl='en',
			safe='on',
			q=query
		)

		async with ctx.channel.typing():
			try:
				async with ctx.http.get(f'http://google.com/search', params=params, headers=headers) as resp:
					if resp.status != 200:
						raise commands.CommandError(f'Query returned status {resp.status} {resp.reason}')

					text = await resp.text()

				soup = BeautifulSoup(text, 'lxml')

				g = soup.find(class_='g', lang=None)

				if g is None:
					raise commands.CommandError('No results found.')

				title = g.h3.string
				link = g.a['href']
				desc = g.find(class_='st').text
				site = urlparse(link).netloc

				embed = discord.Embed(title=title, url=link, description=desc)
				embed.set_footer(text=site)
				await ctx.send(embed=embed)

			except asyncio.TimeoutError:
				raise commands.CommandError('Query timed out.')

	@commands.command()
	@commands.bot_has_permissions(manage_messages=True)
	async def say(self, ctx, channel: discord.TextChannel, *, content: str):
		'''Send a message in a channel.'''

		await ctx.message.delete()
		await channel.send(content)

	@commands.command(aliases=['gh'])
	@commands.bot_has_permissions(embed_links=True)
	async def github(self, ctx, *, query: str):
		'''Google search for GitHub pages.'''

		await ctx.invoke(self.google, query='site:github.com ' + query)

	@commands.command(aliases=['f'])
	@commands.bot_has_permissions(embed_links=True)
	async def forum(self, ctx, *, query: str):
		'''Google search for AutoHotkey pages.'''

		await ctx.invoke(self.google, query='site:autohotkey.com ' + query)

	@commands.command()
	async def status(self, ctx):
		'''Refresh the status of the bot in case Discord cleared it.'''

		await self.bot.change_presence()
		await self.bot.change_presence(activity=BOT_ACTIVITY)

	@commands.command()
	async def pm(self, ctx, user: discord.User, *, content: str):
		'''Private message a user.'''

		await user.send(content)

	@commands.command()
	async def print(self, ctx, *, body: str):
		'''Calls eval but wraps code in print()'''

		await ctx.invoke(self.eval, body=f'pprint({body})')


def setup(bot):
	bot.add_cog(Owner(bot))
