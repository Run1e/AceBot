import discord
from discord.ext import commands

from datetime import datetime

from .base import TogglableCogMixin
from utils.time import pretty_timedelta, pretty_datetime
from utils.database import db


class Seen(TogglableCogMixin):
	'''Keeps track of when members was last seen.'''

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_message(self, ctx):
		if ctx.author.bot or not await self.bot.uses_module(ctx.guild.id, 'seen'):
			return
		await db.scalar(
			'INSERT INTO seen (guild_id, user_id, seen) VALUES ($1, $2, $3) ON CONFLICT (guild_id, user_id) DO UPDATE SET seen=$3',
			ctx.guild.id, ctx.author.id, datetime.now())

	@commands.command()
	async def seen(self, ctx, member: discord.Member):
		'''Check when a member was last seen.'''

		e = discord.Embed()

		e.set_author(
			name=member.display_name,
			icon_url=member.avatar_url
		)

		entry = await db.first('SELECT * FROM seen WHERE guild_id=$1 AND user_id=$2', ctx.guild.id, member.id)

		if entry is None:
			e.description = 'Member has not been seen by the bot yet.'
		else:
			now = datetime.now()
			e.description = f'Seen {pretty_timedelta(now - entry.seen)} ago at {pretty_datetime(entry.seen)}'

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Seen(bot))
