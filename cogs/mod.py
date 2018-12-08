import discord
from discord.ext import commands
from datetime import datetime

from cogs.base import TogglableCogMixin


class Moderator(TogglableCogMixin):
	'''
	Moderation commands.
	
	Only available to members with Ban Members permissions.
	'''

	async def __local_check(self, ctx):
		return await self._is_used(ctx) and ctx.author.permissions_in(ctx.channel).ban_members

	@commands.command()
	async def info(self, ctx, user: discord.Member = None):
		'''Display information about user or self.'''

		if user is None:
			user = ctx.author

		e = discord.Embed(description='This account is a bot.' if user.bot else '')

		e.add_field(name='Status', value=user.status)

		if user.activity:
			e.add_field(name='Activity', value=user.activity)
		if user.nick:
			e.add_field(name='Guild nickname', value=user.nick)

		e.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.avatar_url)

		now = datetime.now()
		created = user.created_at
		joined = user.joined_at

		e.add_field(
			name='Account age',
			value=f'{(now - created).days} days.\nCreated {created.day}/{created.month}/{created.year}'
		)

		e.add_field(
			name='Member for',
			value=f'{(now - joined).days} days.\nJoined {joined.day}/{joined.month}/{joined.year}'
		)

		if len(user.roles) > 1:
			e.add_field(name='Roles', value=', '.join(role.mention for role in reversed(user.roles[1:])))

		e.set_footer(text='ID: ' + str(user.id))

		await ctx.send(embed=e)

	@commands.command()
	@commands.bot_has_permissions(manage_messages=True)
	async def clear(self, ctx, message_count: int = None, user: discord.User = None):
		'''Clear messages, either from user or indiscriminately.'''

		if message_count is None:
			return await ctx.send('Please choose a message count.')

		if message_count > 100:
			return await ctx.send('Please choose a message count below 100.')

		if user is not None:
			check = lambda msg: msg.author == user
		else:
			check = None

		await ctx.message.delete()
		deleted = await ctx.channel.purge(limit=message_count, check=check)

		await ctx.send(f'\U0000274C Deleted {len(deleted)} messages.', delete_after=5)


def setup(bot):
	bot.add_cog(Moderator(bot))
