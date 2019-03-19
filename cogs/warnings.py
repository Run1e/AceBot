import discord, asyncio
from discord.ext import commands
from datetime import datetime

from utils.pager import Pager
from utils.database import db, Warning
from cogs.base import TogglableCogMixin

# https://stackoverflow.com/questions/9647202/ordinal-numbers-replacement
import math
ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(math.floor(n/10)%10!=1)*(n%10<4)*n%10::4])

class WarningPager(Pager):
	async def craft_page(self, e, page, entries):
		e.set_author(name=self.member.display_name, icon_url=self.member.avatar_url)
		e.description = f'All warnings for {self.member.mention}'

		for entry in entries:
			e.add_field()


class Warnings(TogglableCogMixin):
	'''Give warnings to users.'''

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	@commands.command()
	@commands.has_permissions(ban_members=True)
	async def warn(self, ctx, member: discord.Member, *, reason: str):
		'''Warn a user.'''

		await ctx.message.delete()

		await Warning.create(
			guild_id=ctx.guild.id,
			user_id=member.id,
			issuer_id=ctx.author.id,
			made_at=datetime.utcnow(),
			reason=reason
		)

		count = await db.scalar(
			'SELECT COUNT(id) FROM warning WHERE guild_id=$1 AND user_id=$2 ORDER BY id DESC',
			ctx.guild.id, member.id
		)

		await ctx.send(
			f'{member.mention}, you have received your {ordinal(count)} warning:\n```\n{reason}\n```'
		)

	@commands.command()
	@commands.has_permissions(ban_members=True)
	async def warnings(self, ctx, member: discord.Member):
		'''View all of a members warnings.'''

		warns = await db.all('SELECT * FROM warning WHERE guild_id=$1 AND user_id=$2', ctx.guild.id, member.id)

		if not len(warns):
			raise commands.CommandError('No warnings found for this user.')

		p = WarningPager(ctx, warns, per_page=8)
		p.member = member

		await p.go()


def setup(bot):
	bot.add_cog(Warnings(bot))
