import discord
from discord.ext import commands

from datetime import datetime

from cogs.mixins import AceMixin
from utils.time import pretty_timedelta, pretty_datetime


class Seen(AceMixin, commands.Cog):
	'''Keeps track of when members was last seen.'''

	@commands.Cog.listener()
	async def on_message(self, ctx):
		if ctx.author.bot:
			return

		await self.db.execute(
			'INSERT INTO seen (guild_id, user_id, seen) VALUES ($1, $2, $3) ON CONFLICT (guild_id, user_id) DO UPDATE SET seen=$3',
			ctx.guild.id, ctx.author.id, datetime.now()
		)

	@commands.command()
	async def seen(self, ctx, member: discord.User):
		'''Check when a member was last seen.'''

		e = discord.Embed()

		e.set_author(
			name=member.display_name,
			icon_url=member.avatar_url
		)

		seen = await self.db.fetchval(
			'SELECT seen FROM seen WHERE guild_id=$1 AND user_id=$2',
			ctx.guild.id, member.id
		)

		if seen is None:
			e.description = 'Member has not been seen by the bot yet.'
		else:
			now = datetime.now()
			e.description = f'Seen {pretty_timedelta(now - seen)} ago at {pretty_datetime(seen)}'

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Seen(bot))
