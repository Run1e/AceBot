import discord, asyncio, logging, json, re
from discord.ext import commands

from utils.docs_search import docs_search
from utils.string_manip import to_markdown, shorten
from cogs.base import TogglableCogMixin

from html2text import HTML2Text
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

htt = HTML2Text()
htt.body_width = 0

AHK_GUILD_ID = 115993023636176902

# for rss
# FORUM_ID = 517692823621861409
FORUM_ID = 536785342959845386

# for roles
ROLES_CHANNEL = 513071256283906068
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

		channel = self.bot.get_channel(FORUM_ID)

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

		# command not found? docs search it. only if message string is not *only* dots though
		if isinstance(error, commands.CommandNotFound) and len(
				ctx.message.content) > 3 and not ctx.message.content.startswith('..'):
			await ctx.invoke(self.docs, search=ctx.message.content[1:])

	async def on_raw_reaction_add(self, payload):
		if payload.channel_id != ROLES_CHANNEL:
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
		if ctx.channel.id != ROLES_CHANNEL:
			return

		await ctx.message.delete()
		await ctx.channel.purge()

		roles = []
		for role_id in ROLES:
			roles.append(ctx.guild.get_role(role_id))

		e = discord.Embed(description='Click the reactions to add yourselves to a role!')

		for role in roles:
			e.add_field(name=ROLES[role.id], value=role.mention)

		msg = await ctx.send(embed=e)

		for role in roles:
			await msg.add_reaction(ROLES[role.id])

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def docs(self, ctx, *, search):
		'''Search the AutoHotkey documentation.'''

		embed = discord.Embed()
		embed.color = 0x95CD95

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


def setup(bot):
	bot.add_cog(AutoHotkey(bot))
