from datetime import datetime

import discord
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.time import pretty_timedelta, pretty_datetime
from utils.string import po


class WhoIs(AceMixin, commands.Cog):
	'''View info about a member.'''

	def __init__(self, bot):
		super().__init__(bot)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, *, member: discord.Member = None):
		'''Display information about user or self.'''

		member = member or ctx.author

		e = discord.Embed(description='')

		if member.bot:
			e.description = 'This account is a bot.\n\n'

		e.description += member.mention

		e.add_field(name='Status', value=member.status)

		if member.activity:
			e.add_field(name='Activity', value=member.activity.name)

		e.set_author(name=str(member), icon_url=member.avatar_url)

		now = datetime.utcnow()
		created = member.created_at
		joined = member.joined_at

		e.add_field(
			name='Account age',
			value='{0} • Created {1}'.format(pretty_timedelta(now - created), pretty_datetime(created)),
			inline=False
		)

		e.add_field(
			name='Member for',
			value='{0} • Joined {1}'.format(pretty_timedelta(now - joined), pretty_datetime(joined))
		)

		if len(member.roles) > 1:
			e.add_field(name='Roles', value=' '.join(role.mention for role in reversed(member.roles[1:])), inline=False)

		e.set_footer(text='ID: ' + str(member.id))

		await ctx.send(embed=e)

	@commands.command(aliases=['newmembers'])
	@commands.bot_has_permissions(embed_links=True)
	async def newusers(self, ctx, *, count=5):
		'''List newly joined members.'''

		count = min(max(count, 5), 25)

		now = datetime.utcnow()
		e = discord.Embed()

		for idx, member in enumerate(sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)):
			if idx >= count:
				break

			value = 'Joined {0} ago\nCreated {1} ago'.format(pretty_timedelta(now - member.joined_at), pretty_timedelta(now - member.created_at))
			e.add_field(name=po(member), value=value, inline=False)

		await ctx.send(embed=e)

	@commands.command()
	async def avatar(self, ctx, *, member: discord.Member):
		'''Show an enlarged version of a members avatar.'''

		await ctx.send(member.avatar_url)


def setup(bot):
	bot.add_cog(WhoIs(bot))
