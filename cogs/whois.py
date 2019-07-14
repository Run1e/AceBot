import discord
from discord.ext import commands

from datetime import datetime

from cogs.mixins import AceMixin
from utils.time import pretty_timedelta, pretty_datetime


class WhoIs(AceMixin, commands.Cog):
	'''Keeps track of when members was last seen.'''

	MAX_NICKS = 6

	@commands.Cog.listener()
	async def on_message(self, ctx):
		if ctx.author.bot:
			return

		await self.db.execute(
			'INSERT INTO seen (guild_id, user_id, seen) VALUES ($1, $2, $3) ON CONFLICT (guild_id, user_id) '
			'DO UPDATE SET seen=$3',
			ctx.guild.id, ctx.author.id, datetime.now()
		)

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		nicks = [before.display_name]

		if before.display_name != after.display_name:
			nicks.append(after.display_name)

		now = datetime.utcnow()

		last_nick = await self.db.fetchval(
			'SELECT nick FROM nick WHERE guild_id=$1 AND user_id=$2 ORDER BY id DESC',
			before.guild.id, before.id
		)

		for nick in nicks:
			if last_nick != nick:
				await self.db.execute(
					'INSERT INTO nick (guild_id, user_id, nick, stored_at) VALUES ($1, $2, $3, $4)',
					before.guild.id, before.id, nick, now
				)

				last_nick = nick

	@commands.command()
	async def seen(self, ctx, member: discord.Member):
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

	@commands.command()
	async def nicks(self, ctx, member: discord.Member = None):
		'''Lists all known usernames of a member.'''

		member = member or ctx.author

		nicks_data = await self.db.fetch(
			'SELECT nick, stored_at FROM nick WHERE guild_id=$1 AND user_id=$2',
			ctx.guild.id, member.id
		)

		e = discord.Embed()

		e.set_author(
			name=member.display_name,
			icon_url=member.avatar_url
		)

		nicks = []

		for nick in reversed(nicks_data[:-1]):
			nick_actual = nick.get('nick')

			if nick_actual not in nicks:
				if len(nicks) >= self.MAX_NICKS:
					e.description = f'{len(nicks_data) - self.MAX_NICKS - 1} more unlisted found...'
					break

				nicks.append(nick_actual)

				e.add_field(
					name=discord.utils.escape_markdown(nick_actual),
					value='Stored at ' + pretty_datetime(nick.get('stored_at')),
					inline=False
				)

		# else: doesn't work here for some reason, guess I just misunderstand what for: else: does lol
		if not len(e.fields):
			e.description = 'None stored yet.'

		await ctx.send(embed=e)


	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, user: discord.Member = None):
		'''Display information about user or self.'''

		if user is None:
			user = ctx.author

		e = discord.Embed(description='')

		if user.bot:
			e.description = 'This account is a bot.\n\n'

		e.description += user.mention

		e.add_field(name='Status', value=user.status)

		if user.activity:
			e.add_field(name='Activity', value=user.activity)

		e.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.avatar_url)

		now = datetime.utcnow()
		created = user.created_at
		joined = user.joined_at

		e.add_field(
			name='Account age',
			value=f'{pretty_timedelta(now - created)}\nCreated {created.day}/{created.month}/{created.year}'
		)

		e.add_field(
			name='Member for',
			value=f'{pretty_timedelta(now - joined)}\nJoined {joined.day}/{joined.month}/{joined.year}'
		)

		if len(user.roles) > 1:
			e.add_field(name='Roles', value=' '.join(role.mention for role in reversed(user.roles[1:])))

		e.set_footer(text='ID: ' + str(user.id))

		await ctx.send(embed=e)



def setup(bot):
	bot.add_cog(WhoIs(bot))
