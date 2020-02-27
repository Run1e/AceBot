import discord
import asyncpg
import logging

from discord.ext import commands
from typing import Union

from cogs.mixins import AceMixin
from utils.checks import is_mod, is_mod_pred
from utils.string_helpers import present_object

log = logging.getLogger(__name__)


class FeedConverter(commands.Converter):
	async def convert(self, ctx, feed):
		record = await ctx.bot.db.fetchrow(
			'SELECT * FROM feed WHERE guild_id=$1 AND LOWER(name) = $2',
			ctx.guild.id, feed
		)

		if record is None:
			raise commands.CommandError('No feed by that name found.')

		return record


class FeedNameConverter(commands.Converter):
	async def convert(self, ctx, name):
		name = name.lower()

		if len(name) > 32:
			raise commands.CommandError('Feed names can\'t be longer than 32 characters.')

		escape_converter = commands.clean_content(fix_channel_mentions=True, escape_markdown=True)
		if name != await escape_converter.convert(ctx, name):
			raise commands.CommandError('Feed name has disallowed formatting in it.')

		return name


class Feeds(AceMixin, commands.Cog):
	'''Newsletter/feed system.

	When creating a feed a new role is created. This role is given to members who subscribe to the feed. Upon publishing, the published message is posted along with a role mention.
	'''

	@commands.Cog.listener()
	async def on_guild_role_delete(self, role):
		await self.db.execute('DELETE FROM feed WHERE role_id=$1', role.id)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def feeds(self, ctx):
		'''List all feeds in this guild.'''

		records = await self.db.fetch('SELECT name, role_id FROM feed WHERE guild_id=$1', ctx.guild.id)

		if not records:
			raise commands.CommandError('No feeds set up in this server.')

		role_ids = list(role.id for role in ctx.author.roles)

		subbed = list()
		unsubbed = list()

		for r in records:
			if r.get('role_id') in role_ids:
				subbed.append(r.get('name'))
			else:
				unsubbed.append(r.get('name'))

		e = discord.Embed(title=ctx.guild.name + ' Feeds')

		e.add_field(
			name='\N{WHITE HEAVY CHECK MARK} Subscribed',
			value='\n'.join(' • ' + name for name in subbed) if subbed else 'None yet!',
			inline=False
		)

		e.add_field(
			name='\N{CROSS MARK} Unsubscribed',
			value='\n'.join(' • ' + name for name in unsubbed) if unsubbed else 'None!',
			inline=False
		)

		e.set_footer(text='{}sub <feed> to subscribe to a feed.'.format(ctx.prefix))
		e.set_thumbnail(url=ctx.guild.icon_url)

		await ctx.send(embed=e)

	@commands.command()
	@commands.bot_has_permissions(manage_roles=True)
	async def sub(self, ctx, *, feed: FeedConverter):
		'''Subscribe to a feed.'''

		role_id = feed.get('role_id')
		name = feed.get('name')

		role = await self._get_role(ctx, role_id)

		if role in ctx.author.roles:
			raise commands.CommandError('You are already subscribed to this feed.')

		try:
			await ctx.author.add_roles(role, reason='Subscribed to feed.')
		except discord.HTTPException:
			raise commands.CommandError('Failed adding role, make sure bot has Manage Roles permissions.')

		await ctx.send('Subscribed to `{}`.'.format(name))

	@commands.command()
	@commands.bot_has_permissions(manage_roles=True)
	async def unsub(self, ctx, *, feed: FeedConverter):
		'''Unsubscribe from a feed.'''

		role_id = feed.get('role_id')
		name = feed.get('name')

		role = await self._get_role(ctx, role_id)

		if role not in ctx.author.roles:
			raise commands.CommandError('You aren\'t currently subscribed to this feed.')

		try:
			await ctx.author.remove_roles(role, reason='Unsubscribed from feed.')
		except discord.HTTPException:
			raise commands.CommandError('Failed removing role, make sure bot has Manage Roles permissions.')

		await ctx.send('Unsubscribed from `{}`.'.format(name))

	@commands.command()
	@commands.bot_has_permissions(manage_roles=True, manage_messages=True, embed_links=True)
	async def pub(self, ctx, feed: FeedConverter, *, content: str):
		'''Publish to a feed.'''

		role_id = feed.get('role_id')
		channel_id = feed.get('channel_id')
		publisher_id = feed.get('publisher_id')

		async def can_pub():
			if publisher_id is not None:
				if publisher_id == ctx.author.id:
					return True
				elif any(role.id == publisher_id for role in ctx.author.roles):
					return True

			if await is_mod_pred(ctx):
				return True

			return False

		if not await can_pub():
			raise commands.CommandError('You can\'t publish to this feed.')

		role = await self._get_role(ctx, role_id)

		channel = ctx.guild.get_channel(channel_id)
		if channel is None:
			raise commands.CommandError('Feed publish channel not found. Has it been deleted?')

		message = '{0.mention} • *Published by {1.mention}*\n\n{2}'.format(role, ctx.author, content)

		if len(message) > 2000:
			raise commands.CommandError('Final message ends up being above 2000 characters. Please shave off a few.')

		try:
			await role.edit(mentionable=True)
		except discord.HTTPException:
			raise commands.CommandError('Failed making role mentionable, publish aborted.')

		try:
			await channel.send(message)
		except discord.HTTPException:
			await role.edit(mentionable=False)
			raise commands.CommandError(
				'Message failed to send. Make sure bot has permissions to send in the feed channel.'
			)

		try:
			await role.edit(mentionable=False)
		except discord.HTTPException:
			raise commands.CommandError(
				'Message sent successfully, but failed to make role unmentionable. Please do this manually.'
			)

		try:
			await ctx.message.delete()
		except discord.HTTPException:
			pass

		log.info('{} published to feed {} in {}'.format(present_object(ctx.author), feed, present_object(ctx.guild)))

	@commands.group(hidden=True)
	async def feed(self, ctx):
		pass

	@feed.command()
	@is_mod()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def create(self, ctx, feed_name: FeedNameConverter, *, channel: discord.TextChannel):
		'''Create a new feed.'''

		try:
			role = await ctx.guild.create_role(
				name=feed_name,
				reason='New feed created by {0.name}#{0.discriminator}'.format(ctx.author)
			)
		except discord.HTTPException:
			raise commands.CommandError('Unable to create role ``. Make sure bot has Manage Roles permissions.')

		try:
			await self.db.execute(
				'INSERT INTO feed (guild_id, channel_id, role_id, name) VALUES ($1, $2, $3, $4)',
				ctx.guild.id, channel.id, role.id, feed_name
			)
		except asyncpg.UniqueViolationError:
			await role.delete()
			raise commands.CommandError('Feed named `{}` already exists.'.format(role.name))

		await ctx.send('Created feed `{}`'.format(feed_name))

	@feed.command()
	@is_mod()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def delete(self, ctx, *, feed: FeedConverter):
		'''Delete a feed.'''

		role_id = await self.db.fetchval('DELETE FROM feed WHERE id=$1 RETURNING role_id', feed.get('id'))

		role = ctx.guild.get_role(role_id)

		if role is not None:
			try:
				await role.delete(reason='Feed deleted.')
			except discord.HTTPException:
				pass

		await ctx.send('Feed deleted.')

	@feed.group(hidden=True)
	async def edit(self, ctx):
		pass

	@edit.command()
	@is_mod()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def name(self, ctx, feed: FeedConverter, *, feed_name: FeedNameConverter):
		'''Edit the name of a feed.'''

		await self.db.execute('UPDATE feed SET name=$1 WHERE id=$2', feed_name, feed.get('id'))
		await ctx.send('Feed name updated to `{}`'.format(feed_name))

	@edit.command()
	@is_mod()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def channel(self, ctx, feed: FeedConverter, *, channel: discord.TextChannel):
		'''Edit the publishing channel of a feed.'''

		await self.db.execute('UPDATE feed SET channel_id=$1 WHERE id=$2', channel.id, feed.get('id'))
		await ctx.send('Publishing channel of feed `{}` changed to {}'.format(feed.get('name'), channel.mention))

	@edit.command()
	@is_mod()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def publisher(self, ctx, feed: FeedConverter, *, publisher: Union[discord.Member, discord.Role] = None):
		'''Set a member or role that can publish to a feed.'''

		value = publisher.id if publisher is not None else None
		await self.db.execute('UPDATE feed SET publisher_id=$1 WHERE id=$2', value, feed.get('id'))

		if value is None:
			await ctx.send('Publisher cleared for this feed.')
		else:
			fmt = '{0.display_name}#{0.discriminator}' if isinstance(publisher, discord.Member) else '@\u200b{0.name}'
			await ctx.send('{} can now publish to the `{}` feed.'.format(fmt.format(publisher), feed.get('name')))

	async def _get_role(self, ctx, role_id):
		role = ctx.guild.get_role(role_id)

		if role is None:
			raise commands.CommandError('Couldn\'t find the feed role. Has it been deleted?')

		return role


def setup(bot):
	bot.add_cog(Feeds(bot))
