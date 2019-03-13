import discord, asyncio
from discord.ext import commands

from datetime import datetime, timedelta
from sqlalchemy import or_, and_

from .base import TogglableCogMixin
from utils.checks import is_manager
from utils.database import db, StarGuild, StarMessage, Starrers

import logging

log = logging.getLogger(__name__)

MEDALS = [
	'\N{FIRST PLACE MEDAL}',
	'\N{SECOND PLACE MEDAL}',
	'\N{THIRD PLACE MEDAL}',
	'\N{SPORTS MEDAL}',
]

STAR_EMOJI = '\N{WHITE MEDIUM STAR}'
MINIMUM_STARS = 4  # people (excluding starrer) must've starred within
PURGE_TIME = timedelta(days=7)  # days, to avoid message being removed.
PURGE_INTERVAL = 60 * 60  # check once an hour
COOLDOWN_PERIOD = timedelta(minutes=10)


class Starboard(TogglableCogMixin):
	'''Classic starboard.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.bot.loop.create_task(self.purge_stars())

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_reaction(self, event, pl):
		if str(pl.emoji) != STAR_EMOJI or pl.user_id == self.bot.user.id:
			return

		if not await self.bot.uses_module(pl.guild_id, 'starboard'):
			return

		channel = self.bot.get_channel(pl.channel_id)
		if channel is None:
			return

		try:
			message = await channel.get_message(pl.message_id)
		except discord.HTTPException:
			return

		if (datetime.utcnow() - message.created_at).days > 6:
			return

		try:
			await event(message, pl.user_id)
		except commands.CommandError as exc:  # manually print CommandErrors, kinda hacky but works
			orig_channel = self.bot.get_channel(pl.channel_id)
			if orig_channel is not None:
				await orig_channel.send(embed=discord.Embed(description=str(exc)))

	async def on_raw_reaction_add(self, pl):
		await self.on_reaction(self._star, pl)

	async def on_raw_reaction_remove(self, pl):
		await self.on_reaction(self._unstar, pl)

	async def on_raw_message_delete(self, pl):
		'''If a related message is deleted, remove the star.'''

		# do the less resource intensive query to check first
		if not await self.bot.uses_module(pl.guild_id, 'starboard'):
			return

		sm = await self.get_sm(pl.guild_id, pl.message_id)

		if sm is not None:
			try:
				await self.remove_star(sm)
			except:
				pass

	async def _star(self, message, starrer_id):
		# find out if it's adding a new star to an existingly starred message, or an original star

		sm = await self.get_sm(message.guild.id, message.id)

		if sm is None:
			# new star. post it and store it

			star_channel = await self.get_star_channel(message)

			# unless it's a bot message
			if message.author.bot:
				await message.channel.send(
					f'Sorry <@{starrer_id}> - no starring of bot messages!',
					delete_after=10
				)
				return

			# or their own message
			if message.author.id == starrer_id:
				await message.channel.send(
					f'Sorry <@{starrer_id}> - you can\'t star your own message!',
					delete_after=10
				)
				return

			# or if the user has starred something the last (timedelta COOLDOWN) time ago
			test = await StarMessage.query.where(
				and_(
					StarMessage.guild_id == message.guild.id,
					and_(
						StarMessage.starrer_id == starrer_id,
						StarMessage.starred_at > (datetime.utcnow() - COOLDOWN_PERIOD)
					)
				)
			).gino.scalar()

			# or if it's less than 10 mins since their last starring in this guild
			if test is not None:
				await message.channel.send(
					f'<@{starrer_id}> - please wait a bit before starring another message.',
					delete_after=10
				)
				return

			# post and store the starmessage

			star_message = await star_channel.send(
				content=self.get_header(1),
				embed=self.get_embed(message, 1)
			)

			await StarMessage.create(
				author_id=message.author.id,
				guild_id=message.guild.id,
				message_id=message.id,
				channel_id=message.channel.id,
				star_message_id=star_message.id,
				starrer_id=starrer_id,
				starred_at=datetime.utcnow(),
			)

			await star_message.add_reaction('\N{WHITE MEDIUM STAR}')
		else:
			# original starrer can't re-star
			if starrer_id == sm.starrer_id:
				return

			exists = await Starrers.query.where(
				and_(
					Starrers.star_id == sm.id,
					Starrers.user_id == starrer_id
				)
			).gino.scalar()

			if exists:
				return

			if sm.star_message_id == message.id:
				star_message = message
			else:
				# gotta go get the starred message...

				try:
					star_channel = await self.get_star_channel(message)
					star_message = await star_channel.get_message(sm.star_message_id)
				except (commands.CommandError, discord.HTTPException):
					return

			await Starrers.create(
				user_id=starrer_id,
				star_id=sm.id
			)

			stars = await db.scalar('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

			await self.update_star(star_message, stars + 1)

	async def _unstar(self, message, starrer_id):

		sm = await self.get_sm(message.guild.id, message.id)

		if sm is None:
			return

		# get star_message
		if message.id == sm.star_message_id:
			star_message = message
		else:
			try:
				star_channel = await self.get_star_channel(message)
				star_message = await star_channel.get_message(sm.star_message_id)
			except (commands.CommandError, discord.HTTPException):
				return

		if starrer_id == sm.starrer_id:
			if message.id == sm.message_id:
				# starrer un-starred the original message, delete everything
				await self.remove_star(sm, star_message=star_message)
		else:
			# remove *a* star

			await Starrers.delete.where(
				and_(
					Starrers.star_id == sm.id,
					Starrers.user_id == starrer_id
				)
			).gino.status()

			stars = await db.scalar('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

			await self.update_star(star_message, stars + 1)

	@commands.group(hidden=True, aliases=['starboard', 'sb'], invoke_without_command=True)
	@is_manager()
	async def star(self, ctx):
		pass

	@star.command()
	@commands.has_permissions(manage_messages=True)
	async def fix(self, ctx, message_id: int):
		'''Fixes a starred message, re-fetching the original message and refreshing it.'''

		sm = await self.get_sm(ctx.guild.id, message_id)

		if sm is None:
			raise commands.CommandError('Couldn\'t find that starred message!')

		star_channel = await self.get_star_channel(ctx.message)

		try:
			starred_message = await star_channel.get_message(sm.star_message_id)
		except discord.HTTPException:
			raise commands.CommandError('Couldn\'t find message on starboard!')

		orig_channel = ctx.guild.get_channel(sm.channel_id)

		if orig_channel is None:
			raise commands.CommandError('Couldn\'t find original message channel!')

		try:
			orig_message = await orig_channel.get_message(sm.message_id)
		except discord.HTTPException:
			raise commands.CommandError('Couldn\'t find original message!')

		extra = ''
		if sm.starred_at > datetime.utcnow() - PURGE_TIME:
			extra = ' and star count'

			await db.scalar('DELETE FROM starrers WHERE star_id=$1', sm.id)

			star_list = []

			for reaction in orig_message.reactions + starred_message.reactions:
				if reaction.emoji == STAR_EMOJI:
					async for user in reaction.users():
						if user.id in (self.bot.user.id, sm.starrer_id):
							continue
						if user.id not in star_list:
							await Starrers.create(user_id=user.id, star_id=sm.id)
							star_list.append(user.id)

			stars = len(star_list)
		else:
			stars = await db.scalar('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

		try:
			await starred_message.edit(
				content=self.get_header(stars + 1),
				embed=self.get_embed(orig_message, stars + 1)
			)
		except discord.HTTPException:
			raise commands.CommandError('Failed editing starred message.')

		await ctx.send(f'Refreshed starboard message{extra}.')

	@star.command()
	async def show(self, ctx, message_id: int):
		'''Bring up a specific starred message via ID.'''

		sm = await self.get_sm(ctx.guild.id, message_id)

		if sm is None:
			raise commands.CommandError('Couldn\'t find that starred message!')

		star_channel = await self.get_star_channel(ctx.message)

		try:
			starred_message = await star_channel.get_message(sm.star_message_id)
		except discord.HTTPException:
			raise commands.CommandError('Couldn\'t find message on starboard!')

		await ctx.send(content=starred_message.content, embed=starred_message.embeds[0])

	@star.command()
	async def top(self, ctx):
		'''Lists the most starred authors.'''

		# I think this can be done more cleanly, though my SQL skills are lacking
		# if you have improvements, join here and enlighten me pls! :D - https://discord.gg/X7abzRe

		query = '''
			SELECT COALESCE(sm.count + st.count, sm.count), sm.author_id
			FROM
				(SELECT COUNT(id), (SELECT author_id FROM starmessage WHERE starmessage.id=star_id)
				FROM starrers GROUP BY author_id) AS st
			RIGHT JOIN
				(SELECT COUNT(id), author_id FROM starmessage WHERE guild_id=$1 GROUP BY author_id) AS sm
			ON sm.author_id=st.author_id ORDER BY coalesce DESC LIMIT $2;
		'''

		res = await db.all(query, ctx.guild.id, 10)

		if not len(res):
			raise commands.CommandError('None found!')

		e = discord.Embed()
		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

		e.description = '\n'.join(
			f'{MEDALS[min(idx, 3)]} <@{member}> ({stars} stars)'
			for idx, (stars, member) in enumerate(res)
		)

		await ctx.send(embed=e)

	@star.command()
	async def info(self, ctx, message_id: int):
		'''Info about a starred message.'''

		sm = await self.get_sm(ctx.guild.id, message_id)

		if sm is None:
			raise commands.CommandError('Could not find that starred message.')

		star_ret = await db.scalar('SELECT COUNT(id) FROM starrers WHERE star_id=$1', sm.id)

		author = ctx.guild.get_member(sm.author_id)
		stars = star_ret + 1

		e = discord.Embed()
		e.set_author(name=author.display_name, icon_url=author.avatar_url)

		e.add_field(name='Stars', value=self.star_emoji(stars) + ' ' + str(stars))
		e.add_field(name='Starred in', value=f'<#{sm.channel_id}>')
		e.add_field(name='Author', value=f'<@{author.id}>')
		e.add_field(name='Starrer', value=f'<@{sm.starrer_id}>')
		e.add_field(
			name='Context',
			value=f'[Click here](https://discordapp.com/channels/{sm.guild_id}/{sm.channel_id}/{sm.message_id})'
		)

		e.set_footer(text=f'ID: {sm.message_id}')
		e.timestamp = sm.starred_at

		await ctx.send(embed=e)

	@star.command()
	@is_manager()
	async def channel(self, ctx, channel: discord.TextChannel = None):
		'''
		Set the starboard channel.

		Remember only the bot should be allowed to send messages in this channel!
		'''

		async def announce():
			await ctx.send(f'Starboard channel set to {channel.mention}')

		sg = await StarGuild.query.where(StarGuild.guild_id == ctx.guild.id).gino.first()

		if channel is None:
			if sg is None:
				await ctx.send('No starboard set.')
			else:
				channel = self.bot.get_channel(sg.channel_id)
				if channel is None:
					await ctx.send('Starboard channel is set, but I didn\'t manage to find the channel.')
				else:
					await announce()
		else:
			if sg is None:
				await StarGuild.create(
					guild_id=ctx.guild.id,
					channel_id=channel.id
				)
			else:
				await sg.update(channel_id=channel.id).apply()

			await announce()

	@star.command()
	@commands.has_permissions(manage_messages=True)
	async def delete(self, ctx, message_id: int):
		'''Delete a starred message. Manage Messages perms required.'''

		sm = await StarMessage.query.where(
			and_(
				StarMessage.guild_id == ctx.guild.id,
				or_(
					StarMessage.message_id == message_id,
					StarMessage.star_message_id == message_id
				)
			)
		).gino.first()

		if sm is None:
			raise commands.CommandError('Sorry, couldn\'t find a starred message with that ID.')

		await self.remove_star(sm)

		await ctx.send('Removed successfully.')

	@star.command()
	async def random(self, ctx):
		'''View a random starred message.'''

		sm = await db.first('SELECT * FROM starmessage WHERE guild_id=$1 ORDER BY random() LIMIT 1', ctx.guild.id)

		if sm is None:
			raise commands.CommandError('No starred messages in this server!')

		star_channel = await self.get_star_channel(ctx.message)

		try:
			star_message = await star_channel.get_message(sm.star_message_id)
		except discord.HTTPException as exc:
			raise commands.CommandError(str(exc))

		await ctx.send(content=star_message.content, embed=star_message.embeds[0])

	async def update_star(self, star_message, stars):
		'''Updates a previously starred message'''

		embed = star_message.embeds[0]
		embed.colour = self.star_gradient_colour(stars)
		await star_message.edit(content=self.get_header(stars), embed=embed)

	async def remove_star(self, sm, star_channel=None, star_message=None):
		'''
		1. deletes the starrers
		2. deletes the starmessage
		3. attempts to delete the starred message

		raises CommandError if it fails deleting the starred message
		'''

		# delete starrers
		await Starrers.delete.where(Starrers.star_id == sm.id).gino.status()
		await sm.delete()

		# delete the starred message
		if star_message is not None:
			try:
				await star_message.delete()
			except discord.HTTPException as exc:
				raise commands.CommandError(str(exc))
		else:
			if star_channel is None:
				# get the sb chan...
				star_channel_id = await db.scalar('SELECT channel_id FROM starguild WHERE guild_id=$1', sm.guild_id)
				star_channel = self.bot.get_channel(star_channel_id)

				if star_channel is None:
					raise commands.CommandError('Couldn\'t find starboard channel. Has it been set?')

				try:
					star_message = await star_channel.get_message(sm.star_message_id)
				except discord.HTTPException:
					raise commands.CommandError('Could not find starred message. It might already have been deleted?')

			try:
				await star_message.delete()
			except discord.HTTPException:
				raise commands.CommandError('Failed deleting starred message. Please delete it manually!')

	async def get_sm(self, guild_id, message_id):
		return await StarMessage.query.where(
			and_(
				StarMessage.guild_id == guild_id,
				or_(
					StarMessage.message_id == message_id,
					StarMessage.star_message_id == message_id
				)
			)
		).gino.first()

	async def get_star_channel(self, message):
		# get guild starboard channel

		sg = await StarGuild.query.where(StarGuild.guild_id == message.guild.id).gino.first()
		if sg is None:
			raise commands.CommandError('Starboard channel has not yet been set up.')

		if message.channel.id == sg.channel_id:
			star_channel = message.channel
		else:
			star_channel = self.bot.get_channel(sg.channel_id)
			if star_channel is None:
				raise commands.CommandError('Couldn\'t find starboard channel. Has it been deleted?')

		return star_channel

	def star_emoji(self, stars):
		'''
		Stolen from Rapptz, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L141-L149
		'''
		if 5 > stars >= 0:
			return '\N{WHITE MEDIUM STAR}'
		elif 10 > stars >= 5:
			return '\N{GLOWING STAR}'
		elif 25 > stars >= 10:
			return '\N{DIZZY SYMBOL}'
		else:
			return '\N{SPARKLES}'

	def star_gradient_colour(self, stars):
		'''
		Stolen from Rapptz, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L151-L166
		'''

		p = stars / 13
		if p > 1.0:
			p = 1.0

		red = 255
		green = int((194 * p) + (253 * (1 - p)))
		blue = int((12 * p) + (247 * (1 - p)))
		return (red << 16) + (green << 8) + blue

	def get_header(self, stars):
		return f'{self.star_emoji(stars)} **{stars}**'

	def get_embed(self, message, stars):
		'''
		Stolen from Rapptz with minor tweaks, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L168-L193
		'''

		embed = discord.Embed(description=message.content)
		if message.embeds:
			data = message.embeds[0]
			if data.type == 'image':
				embed.set_image(url=data.url)

		if message.attachments:
			file = message.attachments[0]
			if file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
				embed.set_image(url=file.url)
			else:
				embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

		embed.set_author(
			name=message.author.display_name,
			icon_url=message.author.avatar_url_as(format='png'),
			url=f'https://discordapp.com/channels/{message.guild.id}/{message.channel.id}/{message.id}'
		)

		embed.set_footer(text=f'ID: {message.id}')
		embed.timestamp = message.created_at
		embed.colour = self.star_gradient_colour(stars)
		return embed

	async def purge_stars(self):
		while True:
			await asyncio.sleep(PURGE_INTERVAL)

			try:
				query = '''
					SELECT id, channel_id, star_message_id
					FROM starmessage
					WHERE (SELECT COUNT(id) from starrers where starrers.star_id=starmessage.id) < $1
					AND starred_at < $2
				'''

				# gets all stars older than a week with less than 4 stars
				star_list = await db.all(query, MINIMUM_STARS, datetime.utcnow() - PURGE_TIME)

				for star in star_list:
					# delete discord starmessage, starrers and starmessage
					await Starrers.delete.where(Starrers.star_id == star[0]).gino.status()
					await StarMessage.delete.where(StarMessage.id == star[0]).gino.status()

					# delete starred message in star channel
					channel = self.bot.get_channel(star[1])
					if channel is None:
						continue

					sg = await StarGuild.query.where(StarGuild.guild_id == channel.guild.id).gino.first()
					if sg is None:
						continue

					star_channel = self.bot.get_channel(sg.channel_id)
					if star_channel is None:
						continue
					try:
						star_message = await star_channel.get_message(star[2])
					except discord.NotFound:
						continue

					try:
						await star_message.delete()
					except discord.HTTPException:
						continue

			except (SyntaxError, ValueError, AttributeError) as exc:
				raise exc
			except Exception:
				pass


def setup(bot):
	bot.add_cog(Starboard(bot))
