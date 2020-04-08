import discord
from discord.ext import commands

from datetime import datetime

from cogs.mixins import AceMixin
from cogs.ahk.ids import AHK_GUILD_ID
from utils.time import pretty_timedelta, pretty_datetime

MAX_NICKS = 6


def is_ahk_guild():
	async def pred(ctx):
		return ctx.guild.id == AHK_GUILD_ID
	return commands.check(pred)


class WhoIs(AceMixin, commands.Cog):
	'''Keeps track of when members was last seen.'''

	def __init__(self, bot):
		super().__init__(bot)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, member: discord.Member = None):
		'''Display information about user or self.'''

		member = member or ctx.author

		e = discord.Embed(description='')

		if member.bot:
			e.description = 'This account is a bot.\n\n'

		e.description += member.mention

		e.add_field(name='Status', value=member.status)

		if member.activity:
			e.add_field(name='Activity', value=member.activity.name)

		e.set_author(name=f'{member.name}#{member.discriminator}', icon_url=member.avatar_url)

		now = datetime.utcnow()
		created = member.created_at
		joined = member.joined_at

		e.add_field(
			name='Account age',
			value=f'{pretty_timedelta(now - created)}\nCreated {created.day}/{created.month}/{created.year}'
		)

		e.add_field(
			name='Member for',
			value=f'{pretty_timedelta(now - joined)}\nJoined {joined.day}/{joined.month}/{joined.year}'
		)

		if len(member.roles) > 1:
			e.add_field(name='Roles', value=' '.join(role.mention for role in reversed(member.roles[1:])))

		e.set_footer(text='ID: ' + str(member.id))

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(WhoIs(bot))
