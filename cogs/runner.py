import discord
import io

from discord.ext import commands
from discord.mixins import Hashable
from datetime import datetime

from utils.lookup import DiscordLookup
from cogs.mixins import AceMixin
from cogs.ahk.ids import STAFF_ROLE_ID
from utils.pager import Pager
from utils.string_helpers import shorten
from utils.time import pretty_datetime


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


class Runner(AceMixin, commands.Cog):
	DISCORD_BASE_TYPES = (
		discord.Object, discord.Emoji, discord.abc.Messageable, discord.mixins.Hashable
	)

	async def cog_check(self, ctx):
		return await ctx.bot.is_owner(ctx.author) # or any(role.id == STAFF_ROLE_ID for role in ctx.author.roles)

	@commands.command()
	async def get(self, ctx, *, query: commands.clean_content):
		'''Run a meta-python query.'''

		try:
			res = DiscordLookup(ctx, query).run()
		except Exception as exc:
			raise commands.CommandError('{}\n\n{}'.format(exc.__class__.__name__, str(exc)))

		if res is None or (isinstance(res, list) and not res):
			raise commands.CommandError('No results.')

		if isinstance(res, self.DISCORD_BASE_TYPES):
			res = [res]

		if isinstance(res, list) and isinstance(res[0], self.DISCORD_BASE_TYPES):
			p = DiscordObjectPager(ctx, entries=res, per_page=1)
			await p.go()
		else:
			if isinstance(res, int):
				await ctx.send('`{}`'.format(res))
			else:
				wrapped = '```{}```'.format(res)
				if len(wrapped) > 2000:
					fp = io.BytesIO(str(res).encode('utf-8'))
					await ctx.send('Log too large...', file=discord.File(fp, 'results.txt'))
				else:
					await ctx.send(wrapped)


def setup(bot):
	bot.add_cog(Runner(bot))
