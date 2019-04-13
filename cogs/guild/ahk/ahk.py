import discord, asyncio, logging
from discord.ext import commands

from docs_parser import parse_docs
from utils.database import db, DocsEntry, DocsNameEntry, DocsSyntaxEntry, DocsParamEntry
from cogs.guild.ahk.ids import *
from utils.string_manip import html2markdown, shorten
from cogs.base import TogglableCogMixin

from html2text import HTML2Text
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone


htt = HTML2Text()
htt.body_width = 0

log = logging.getLogger(__name__)

ROLES = {
	345652145267277836: '💻',  # helper
	513078270581932033: '🕹',  # lounge
	513111956425670667: '🇭',  # hotkey crew
	513111654112690178: '🇬',  # gui crew
	513111541663662101: '🇴',  # oop crew
	513111591361970204: '🇷'  # regex crew
}


class AutoHotkey(TogglableCogMixin):
	'''Commands for the AutoHotkey server.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.bot.loop.create_task(self.rss())

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def rss(self):

		url = 'https://www.autohotkey.com/boards/feed'

		channel = self.bot.get_channel(FORUM_CHAN_ID)

		def parse_date(date_str):
			date_str = date_str.strip()
			return datetime.strptime(date_str[:-3] + date_str[-2:], "%Y-%m-%dT%H:%M:%S%z")

		old_time = datetime.now(tz=timezone(timedelta(hours=1))) - timedelta(minutes=1)

		while True:
			await asyncio.sleep(10 * 60)

			try:
				async with self.bot.aiohttp.request('get', url) as resp:
					if resp.status != 200:
						continue
					xml_rss = await resp.text('UTF-8')

				xml = BeautifulSoup(xml_rss, 'xml')

				for entry in xml.find_all('entry')[::-1]:
					time = parse_date(str(entry.updated.text))
					title = htt.handle(str(entry.title.text))
					content = shorten(str(entry.content.text), 512, 8)

					if time > old_time and '• Re: ' not in title:
						e = discord.Embed(
							title=title,
							description=html2markdown(content.split('Statistics: ')[0], big_box=True),
							url=entry.id.text
						)

						e.add_field(name='Author', value=str(entry.author.text))
						e.add_field(name='Forum', value=str(entry.category['label']))

						e.timestamp = time

						if channel is not None:
							await channel.send(embed=e)

						old_time = time
			except (SyntaxError, ValueError, AttributeError) as exc:
				raise exc
			except Exception:
				pass

	async def on_command_error(self, ctx, error):
		if not hasattr(ctx, 'guild') or ctx.guild.id != AHK_GUILD_ID:
			return

		if not await self.bot.blacklist(ctx):
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(
				ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def on_raw_reaction_add(self, payload):
		if payload.channel_id != ROLES_CHAN_ID:
			return

		channel = self.bot.get_channel(payload.channel_id)
		msg = await channel.get_message(payload.message_id)
		if msg.author.id != self.bot.user.id:
			return

		guild = self.bot.get_guild(payload.guild_id)
		member = guild.get_member(payload.user_id)

		if member.bot:
			return

		await msg.remove_reaction(payload.emoji, member)

		action = None

		for role_id, emoji in ROLES.items():
			if emoji == str(payload.emoji):
				role = guild.get_role(role_id)
				action = True
				desc = f'{member.mention} -> {role.mention}'
				if role in member.roles:
					await member.remove_roles(role)
					title = 'Removed Role'
				else:
					await member.add_roles(role)
					title = 'Added Role'

		if action:
			log.info('{} {} {} {}'.format(title, role.name, 'to' if title == 'Added Role' else 'from', member.name))
			await channel.send(embed=discord.Embed(title=title, description=desc), delete_after=5)

	@commands.command(hidden=True)
	@commands.is_owner()
	async def roles(self, ctx):
		if ctx.channel.id != ROLES_CHAN_ID:
			return

		await ctx.message.delete()
		await ctx.channel.purge()

		roles = []
		for role_id in ROLES:
			roles.append(ctx.guild.get_role(role_id))

		e = discord.Embed(description='Click the reactions to give yourself a role!')

		for role in roles:
			e.add_field(name=ROLES[role.id], value=role.mention)

		msg = await ctx.send(embed=e)

		for role in roles:
			await msg.add_reaction(ROLES[role.id])

	@commands.command(aliases=['rtfm'])
	@commands.bot_has_permissions(embed_links=True)
	async def docs(self, ctx, *, search):
		'''Search the AutoHotkey documentation.'''

		search = search.lower()

		res = await db.first(
			'SELECT docs_id, name FROM docs_name ORDER BY word_similarity(name, $1) DESC LIMIT 1',
			search
		)

		if res is None:
			raise commands.CommandError('Sorry, couldn\'t find an entry similar to that.')

		docs_id, name = res

		e = discord.Embed()
		e.color = 0x95CD95

		docs = await db.first('SELECT * FROM docs WHERE id=$1', docs_id)
		syntax = await db.first('SELECT * FROM docs_syntax WHERE docs_id=$1', docs.id)

		e.title = name
		e.url = f'https://autohotkey.com/docs/{docs.page}'
		e.description = docs.desc or 'None for this page.'
		e.set_footer(text='autohotkey.com', icon_url='https://www.autohotkey.com/favicon.ico')

		if syntax is not None:
			e.add_field(
				name='Syntax',
				value=f'```autoit\n{syntax.syntax}```'
			)

		await ctx.send(embed=e)

	@commands.command()
	@commands.is_owner()
	async def build(self, ctx, download : bool = True):
		async def on_update(text):
			await ctx.send(text)

		async def handler(names, page, desc=None, syntax=None, params=None):

			# ignore everything that has to do with examples
			for name in names:
				if 'example' in name.lower():
					return

			docs_id = await db.scalar('SELECT id FROM docs WHERE page=$1', page)

			if docs_id is None:
				doc = await DocsEntry.create(page=page, desc=desc)
				docs_id = doc.id

			for name in names:
				await DocsNameEntry.create(docs_id=docs_id, name=name)

			if syntax is not None:
				await DocsSyntaxEntry.create(docs_id=docs_id, syntax=syntax)

			if params is not None:
				for name, value in params.items():
					await DocsParamEntry.create(docs_id=docs_id, name=name, value=value)

		await db.status('TRUNCATE docs_name, docs_syntax, docs_param, docs RESTART IDENTITY')

		try:
			await parse_docs(handler, on_update, download)
		except Exception as exc:
			raise commands.CommandError(str(exc))


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
