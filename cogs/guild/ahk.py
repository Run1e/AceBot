import discord, asyncio
from discord.ext import commands

from utils.docs_search import docs_search
from utils.string_manip import welcomify, to_markdown, shorten
from cogs.base import TogglableCogMixin

from aiohttp.client_exceptions import ClientError
from html2text import HTML2Text
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

htt = HTML2Text()
htt.body_width = 0

GENERAL_ID = 115993023636176902
STAFF_ID = 311784919208558592
MEMBER_ID = 509526426198999040

WELCOME_MSG = '''
Welcome to our Discord community {user}!
A collection of useful tips are in <#407666416297443328> and recent announcements can be found in <#367301754729267202>.
'''

#FORUM_ID = 517692823621861409
FORUM_ID = 536785342959845386

class AutoHotkey(TogglableCogMixin):
	'''Commands for the AutoHotkey guild.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.bot.loop.create_task(self.rss())

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_command_error(self, ctx, error):
		if ctx.guild.id != 115993023636176902:
			return

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(
				ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def rss(self):

		url = 'https://www.autohotkey.com/boards/feed'

		channel = self.bot.get_channel(FORUM_ID)

		def parse_date(date_str):
			date_str = date_str.strip()
			return datetime.strptime(date_str[:-6], "%Y-%m-%dT%H:%M:%S") + timedelta(hours=6)

		old_time = datetime.now() - timedelta(minutes=1)

		while True:
			await asyncio.sleep(5 * 60)

			try:
				async with self.bot.aiohttp.request('get', url) as resp:
					if resp.status != 200:
						continue
					xml_rss = await resp.text()

				xml = BeautifulSoup(xml_rss, 'xml')

				for entry in xml.find_all('entry')[::-1]:
					time = parse_date(entry.updated.text)
					title = htt.handle(entry.title.text)
					content = shorten(entry.content.text, 512, 8)

					if time > old_time and '• Re: ' not in title:
						e = discord.Embed(
							title=title,
							description=to_markdown(content.split('Statistics: ')[0]),
							url=entry.id.text
						)

						e.add_field(name='Author', value=entry.author.text)
						e.add_field(name='Forum', value=entry.category['label'])
						e.set_footer(text=str(time) + ' CEST')

						if channel is not None:
							await channel.send(embed=e)

						old_time = time

			except (discord.HTTPException, UnicodeDecodeError, ClientError):
				continue

	@commands.command()
	async def docs(self, ctx, *, search):
		'''Search the AutoHotkey documentation.'''

		embed = discord.Embed()
		results = docs_search(search)

		if not len(results):
			raise commands.CommandError('No documentation pages found.')

		elif len(results) == 1:
			for title, obj in results.items():
				embed.title = obj.get('syntax', title)
				embed.description = obj['desc']
				if 'dir' in obj:
					embed.url = f"https://autohotkey.com/docs/{obj['dir']}"

		else:
			for title, obj in results.items():
				value = obj['desc']
				if 'dir' in obj:
					value += f"\n[Documentation](https://autohotkey.com/docs/{obj['dir']})"
				embed.add_field(
					name=obj.get('syntax', title),
					value=value
				)

		await ctx.send(embed=embed)

	@commands.command(hidden=True, aliases=['app'])
	@commands.has_role(STAFF_ID)
	async def approve(self, ctx, member: discord.Member):
		'''Approve member.'''

		try:
			member_role = ctx.guild.get_role(MEMBER_ID)
			if member_role is None:
				raise commands.CommandError('Couldn\'t find Member role.')

			await member.add_roles(member_role, reason=f'Approved by {ctx.author.name}')

		except Exception as exc:
			raise commands.CommandError('Failed adding member role.\n\nError:\n' + str(exc))

		await ctx.send(f'{member.display_name} approved.')

		general_channel = ctx.guild.get_channel(GENERAL_ID)
		if general_channel is None:
			raise commands.CommandError('Couldn\'t find the #general channel.')

		await asyncio.sleep(3)
		await general_channel.send(welcomify(member, ctx.guild, WELCOME_MSG))


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
