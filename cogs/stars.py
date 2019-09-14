import discord
import logging

from discord.ext import commands, tasks
from datetime import datetime, timedelta
from asyncpg.exceptions import UniqueViolationError

from utils.fakectx import FakeContext
from utils.checks import is_mod, is_mod_pred
from utils.time import pretty_timedelta
from utils.prompter import admin_prompter
from utils.converters import TimeMultConverter, TimeDeltaConverter
from utils.configtable import ConfigTable, StarboardConfigRecord
from utils.prompter import prompter
from cogs.mixins import AceMixin

log = logging.getLogger(__name__)
STAR_EMOJI = '\N{WHITE MEDIUM STAR}'
STAR_COOLDOWN = timedelta(minutes=3)

SB_NOT_SET_ERROR = commands.CommandError('No starboard channel has been set yet.')
SB_NOT_FOUND_ERROR = commands.CommandError('Starboard channel previously set but not found, please set it again.')
SB_LOCKED_ERROR = commands.CommandError('Starboard has been locked and can not be used at the moment.')
SB_ORIG_MSG_NOT_FOUND_ERROR = commands.CommandError('Could not find original message.')
SB_STAR_MSG_NOT_FOUND_ERROR = commands.CommandError('Could not find starred message.')


class StarConverter(commands.Converter):
	async def convert(self, ctx, msg_id):
		try:
			msg_id = int(msg_id)
		except ValueError:
			raise commands.CommandError('ID has to be integer value.')

		row = await ctx.bot.db.fetchrow(
			'SELECT * FROM star_msg WHERE guild_id=$1 AND (message_id=$2 OR star_message_id=$2)',
			ctx.guild.id, msg_id
		)

		if row is None:
			raise commands.CommandError('Starred message with that ID was not found.')

		return row


class Starboard(AceMixin, commands.Cog):
	'''Classic Starboard.
	
	You can star messages in two ways:
	1. Reacting to a message with the \N{WHITE MEDIUM STAR} emoji
	2. Getting the message ID and doing `star <message_id>`
	'''

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(bot, table='starboard', primary='guild_id', record_class=StarboardConfigRecord)

		self.purge_query = '''
			SELECT id, guild_id, channel_id, star_message_id
			FROM star_msg
			WHERE guild_id = $1
			AND starred_at < $2
			AND (SELECT COUNT(id) from starrers where starrers.star_id=star_msg.id) < $3
		'''

		self.purger.start()

	@tasks.loop(minutes=10)
	async def purger(self):
		'''Purges old and underperforming stars depending on guild starboard settings.'''

		boards = await self.db.fetch(
			'SELECT guild_id, channel_id, threshold, max_age FROM starboard WHERE locked=$1', False
		)

		now = datetime.utcnow()
		to_delete = list()

		for board in boards:
			rows = await self.db.fetch(
				self.purge_query, board.get('guild_id'), now - board.get('max_age'), board.get('threshold') - 1
			)

			if rows:
				star_channel = self.bot.get_channel(board.get('channel_id'))
				if star_channel is None:
					continue

			for row in rows:
				to_delete.append(row.get('id'))

				try:
					star_message = await star_channel.fetch_message(row.get('star_message_id'))
				except discord.HTTPException:
					continue

				try:
					await star_message.delete()
				except discord.HTTPException:
					pass

		if to_delete:
			await self.db.execute('DELETE FROM starrers WHERE star_id=ANY($1::bigint[])', to_delete)
			await self.db.execute('DELETE FROM star_msg WHERE id=ANY($1::bigint[])', to_delete)

	async def get_board(self, ctx):
		sc = await self.config.get_entry(ctx.guild.id, construct=False)

		if sc is None:
			raise commands.CommandError('Please set up a starboard using `{}star create` first.'.format(ctx.prefix))

		return sc

	@commands.group(name='star', invoke_without_command=True)
	@commands.bot_has_permissions(embed_links=True, add_reactions=True)
	async def _star(self, ctx, *, message_id: discord.Message):
		'''Star a message by ID.'''

		await self._on_star_event_meta(self._on_star, message_id, ctx.author)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True, add_reactions=True)
	async def unstar(self, ctx, *, message_id: discord.Message):
		'''Unstar a message by ID.'''

		await self._on_star_event_meta(self._on_unstar, message_id, ctx.author)

	@_star.command()
	@is_mod()
	@commands.bot_has_permissions(
		manage_messages=True, add_reactions=True, manage_channels=True, embed_links=True, manage_roles=True
	)
	async def create(self, ctx):
		'''Creates a new starboard.'''

		sc = await self.config.get_entry(ctx.guild.id)

		if sc.channel is not None:
			raise commands.CommandError('Starboard already exists -> {}'.format(sc.channel.mention))

		if sc.channel_id is not None:
			result = await prompter(
				ctx, title='The previous starboard seems to have been deleted.',
				prompt='Do you want to create a new one?'
			)

			if not result:
				raise commands.CommandError('Aborted starboard creation.')

		overwrites = {
			ctx.me: discord.PermissionOverwrite(
				read_messages=True,
				send_messages=True,
				manage_messages=True,
				embed_links=True,
				read_message_history=True,
				add_reactions=True
			),
			ctx.guild.default_role: discord.PermissionOverwrite(
				read_messages=True,
				send_messages=False,
				read_message_history=True,
				add_reactions=True
			)
		}

		reason = '{} (ID: {}) has created a starboard channel.'.format(ctx.author.display_name, ctx.author.id)

		try:
			channel = await ctx.guild.create_text_channel(name='starboard', overwrites=overwrites, reason=reason)
		except discord.HTTPException:
			raise commands.CommandError('An unexpected error happened when creating the starboard channel.')

		await sc.update(channel_id=channel.id)

		await ctx.send('Starboard channel created! {}'.format(channel.mention))


	@_star.command()
	@commands.bot_has_permissions(embed_links=True)
	async def show(self, ctx, *, message_id: StarConverter):
		'''Bring up a starred message by ID.'''

		row = message_id

		star_channel = await self._get_star_channel(ctx.guild)

		try:
			message = await star_channel.fetch_message(row.get('star_message_id'))
		except discord.HTTPException:
			raise SB_STAR_MSG_NOT_FOUND_ERROR

		await ctx.send(content=message.content, embed=message.embeds[0])

	@_star.command()
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, *, message_id: StarConverter):
		'''Show info about a starred message.'''

		row = message_id

		star_ret = await self.db.fetchval('SELECT COUNT(id) FROM starrers WHERE star_id=$1', row.get('id'))

		author = await ctx.guild.fetch_member(row.get('user_id'))
		stars = star_ret + 1

		e = discord.Embed()
		e.set_author(name=author.display_name, icon_url=author.avatar_url)

		e.add_field(name='Stars', value=self.star_emoji(stars) + ' ' + str(stars))
		e.add_field(name='Starred in', value='<#{}>'.format(row.get('channel_id')))
		e.add_field(name='Author', value=f'<@{author.id}>')
		e.add_field(name='Starrer', value='<@{}>'.format(row.get('starrer_id')))
		e.add_field(
			name='Context',
			value='[Click here!](https://discordapp.com/channels/{}/{}/{})'.format(
				row.get('guild_id'), row.get('channel_id'), row.get('message_id')
			)
		)

		e.set_footer(text='ID: {}'.format(row.get('message_id')))
		e.timestamp = row.get('starred_at')

		await ctx.send(embed=e)

	@_star.command()
	@commands.bot_has_permissions(embed_links=True)
	async def starrers(self, ctx, *, message_id: StarConverter):
		'''List every starrer of a starred message.'''

		row = message_id

		starrers = await self.db.fetch('SELECT user_id FROM starrers WHERE star_id=$1', row.get('id'))

		e = discord.Embed()

		e.add_field(name='Original starrer', value='<@{}>'.format(row.get('starrer_id')), inline=False)

		if starrers:
			desc = '\n'.join('<@{}>'.format(srow.get('user_id')) for srow in starrers)
		else:
			desc = 'No one yet!'

		e.add_field(name='Additional starrers', value=desc, inline=False)

		e.set_footer(text='Total: {}'.format(len(starrers) + 1))

		await ctx.send(embed=e)

	@_star.command()
	@commands.bot_has_permissions(embed_links=True)
	async def random(self, ctx):
		'''Show a random starred message.'''

		entry = await self.db.fetchrow('SELECT * FROM star_msg ORDER BY random() LIMIT 1')

		if entry is None:
			raise commands.CommandError('No starred messages to pick from.')

		await ctx.invoke(self.show, message_id=entry)

	@_star.command()
	@is_mod()
	async def threshold(self, ctx, *, limit: int = None):
		'''Set the minimum amount of stars needed for a starred message to remain on the starboard after a week has passed'''

		sc = await self.get_board(ctx)

		print(sc)

		if limit is None:
			limit = sc.threshold
		else:
			await sc.update(threshold=limit)

		await ctx.send(f'Star threshold set to `{limit}`')

	@_star.command()
	@is_mod()
	async def lifespan(self, ctx, amount: TimeMultConverter = None, *, unit: TimeDeltaConverter = None):
		'''Starred messages with less than `threshold` stars after this period are deleted from the starboard. Messages older than this cannot be starred.'''

		if unit is None and amount is not None:
			raise commands.CommandError('Malformed input.')

		sc = await self.get_board(ctx)

		if unit is not None and amount is not None:
			age = amount * unit

			if age < timedelta(days=1):
				raise commands.CommandError('Please set to at least more than 1 day.')

			await sc.update(max_age=age)
		else:
			age = sc.max_age

		await ctx.send(f'Star lifespan set to {pretty_timedelta(age)}')

	@_star.command()
	@is_mod()
	async def fix(self, ctx, *, message_id: StarConverter):
		'''Refreshes message content and re-counts starrers.'''

		row = message_id

		channel = ctx.guild.get_channel(row.get('channel_id'))
		if channel is None:
			raise SB_ORIG_MSG_NOT_FOUND_ERROR

		try:
			message = await channel.fetch_message(row.get('message_id'))
		except discord.HTTPException:
			raise SB_ORIG_MSG_NOT_FOUND_ERROR

		star_channel = await self._get_star_channel(ctx.guild)

		try:
			star_message = await star_channel.fetch_message(row.get('star_message_id'))
		except discord.HTTPException:
			raise SB_STAR_MSG_NOT_FOUND_ERROR

		added = 0

		for reaction in message.reactions + star_message.reactions:
			if str(reaction.emoji) != STAR_EMOJI:
				continue

			async for user in reaction.users():
				if user.bot:
					continue

				if user.id == row.get('starrer_id'):
					continue

				try:
					await self.db.execute(
						'INSERT INTO starrers (star_id, user_id) VALUES ($1, $2)',
						row.get('id'), user.id
					)

					added += 1
				except UniqueViolationError:
					pass

		star_count = await self.db.fetchval('SELECT COUNT(*) FROM starrers WHERE star_id=$1', row.get('id'))

		new_embed = self.get_embed(message, star_count + 1)
		edited = new_embed.description != star_message.embeds[0].description

		await star_message.edit(
			content=self.get_header(message.id, star_count + 1),
			embed=self.get_embed(message, star_count + 1)
		)

		parts = list()
		if edited:
			parts.append('Content updated')
		if added > 0:
			parts.append('{} star{} added'.format(added, 's' if added > 1 else ''))
		if not parts:
			parts.append('Nothing to fix/update')

		await ctx.send(', '.join(parts) + '.')

	@_star.command()
	@commands.bot_has_permissions(manage_messages=True)
	async def delete(self, ctx, *, message_id: StarConverter):
		'''Remove a starred message. The author, starrer or any moderator can use this on any given starred message.'''

		row = message_id

		if ctx.author.id not in (row.get('user_id'), row.get('starrer_id')):
			if not await is_mod_pred(ctx):
				return
			elif not await admin_prompter(ctx):
				return

		await self.db.execute('DELETE FROM starrers WHERE star_id=$1', row.get('id'))
		await self.db.execute('DELETE FROM star_msg WHERE id=$1', row.get('id'))

		star_channel = await self._get_star_channel(ctx.guild)

		try:
			star_message = await star_channel.fetch_message(row.get('star_message_id'))
			await star_message.delete()
		except discord.HTTPException:
			pass

		await ctx.send('Star deleted.')

	@_star.command()
	@is_mod()
	async def lock(self, ctx):
		'''Lock the starboard.'''

		sc = await self.get_board(ctx)

		await sc.update(locked=True)

		await ctx.send('Starboard locked.')

	@_star.command()
	@is_mod()
	async def unlock(self, ctx):
		'''Unlock the starboard.'''

		sc = await self.get_board(ctx)

		await sc.update(locked=False)

		await ctx.send('Starboard unlocked.')

	async def _on_star(self, starrer, star_channel, message, star_message, record):
		if record is not None:
			# this message has been starred before.

			# original starrer can't restar
			if starrer.id == record.get('starrer_id'):
				return

			# author of message can't star
			if starrer.id == record.get('user_id'):
				return

			# can't restar if already starred
			if await self.db.fetchval(
					'SELECT user_id FROM starrers WHERE star_id=$1 AND user_id=$2',
					record.get('id'), starrer.id
			):
				return

			# insert into starrers table
			await self.db.execute(
				'INSERT INTO starrers (star_id, user_id) VALUES ($1, $2)',
				record.get('id'), starrer.id
			)

			# and update the starred message
			starrer_count = await self.db.fetchval(
				'SELECT COUNT(*) FROM starrers WHERE star_id=$1',
				record.get('id')
			)

			await self.update_star_count(record.get('message_id'), star_message, starrer_count + 1)

		else:
			# new star. post it and store it

			if message is None:
				return # undef behaviour

			if message.author == starrer:
				raise commands.CommandError('Can\'t star your own message.')

			if message.channel.is_nsfw() and not star_message.channel.is_nsfw():
				raise commands.CommandError('Can\'t star message from nsfw channel into non-nsfw starboard.')

			if not len(message.content) and not len(message.attachments):
				raise commands.CommandError('Can\'t star this message because it has no starrable content.')

			# make sure the starrer isn't starring too quickly
			prev_time = await self.db.fetchval(
				'SELECT starred_at FROM star_msg WHERE guild_id=$1 AND starrer_id=$2 ORDER BY id DESC LIMIT 1',
				message.guild.id, starrer.id
			)

			if prev_time is not None and datetime.utcnow() - prev_time < STAR_COOLDOWN:
				raise commands.CommandError('Please wait a bit before starring again.')

			# post it to the starboard
			try:
				star_message = await star_channel.send(
					self.get_header(message.id, 1),
					embed=self.get_embed(message, 1)
				)
			except discord.HTTPException:
				raise commands.CommandError('Failed posting to starboard.\nMake sure the bot has permissions to post there.')

			# save it to db
			await self.db.execute(
				'INSERT INTO star_msg (guild_id, channel_id, user_id, message_id, star_message_id, starred_at, '
				'starrer_id) VALUES ($1, $2, $3, $4, $5, $6, $7)',
				message.guild.id, message.channel.id, message.author.id, message.id, star_message.id,
				datetime.utcnow(), starrer.id
			)

			# add the star emoji reaction to the starboard message
			try:
				await star_message.add_reaction(STAR_EMOJI)
			except discord.HTTPException:
				pass

	async def _on_unstar(self, starrer, star_channel, message, star_message, record):
		if record:
			result = await self.db.execute(
				'DELETE FROM starrers WHERE star_id=$1 AND user_id=$2',
				record.get('id'), starrer.id
			)

			# if nothing was deleted, the star message doesn't need to be updated
			if result == 'DELETE 0':
				return

			# otherwise we need to update the star count
			starrer_count = await self.db.fetchval(
				'SELECT COUNT(*) FROM starrers WHERE star_id=$1',
				record.get('id')
			)

			await self.update_star_count(record.get('message_id'), star_message, starrer_count + 1)

		else:
			pass # ???

	async def _on_star_event_meta(self, event, message, starrer):
		row = await self.db.fetchrow(
			'SELECT * FROM star_msg WHERE guild_id=$1 AND (message_id=$2 OR star_message_id=$2)',
			message.guild.id, message.id
		)

		sc = await self.config.get_entry(message.guild.id, construct=False)

		if sc is None:
			return

		# stop if starboard is not set up
		if sc.channel_id is None:
			raise SB_NOT_SET_ERROR

		# stop if starboard is locked
		if sc.locked:
			raise SB_LOCKED_ERROR

		# stop if attempted star is too old
		if datetime.utcnow() - sc.max_age > message.created_at:
			raise commands.CommandError(
				'Stars can\'t be added or removed from messages older than {}.'.format(pretty_timedelta(sc.max_age))
			)

		if message.channel.id == sc.channel_id:
			# if the reaction event happened in the starboard channel we already have a reference
			# to both the channel and starred message
			star_channel = message.channel
			star_message = message
			message = None
		else:
			# otherwise we have to fetch the star channel from the db id
			star_channel = message.guild.get_channel(sc.channel_id)

			# fail if we can't find it...
			if star_channel is None:
				raise SB_NOT_FOUND_ERROR

			# we should also find the starred message
			if row is not None:
				# if we have the record we catch fetch the starred message
				try:
					star_message = await star_channel.fetch_message(row.get('star_message_id'))
				except discord.HTTPException:
					raise SB_STAR_MSG_NOT_FOUND_ERROR
			else:
				# if row is none, this reaction did not happen in the starboard and we don't have a ref
				star_message = None

		# trigger event
		# message and star_message can be populated, or *one* of them can be None
		await event(starrer, star_channel, message, star_message, row)

	async def _on_star_event(self, payload, event):
		# only listen for star emojis
		if str(payload.emoji) != STAR_EMOJI:
			return

		# attempt to get the message
		channel = self.bot.get_channel(payload.channel_id)
		if channel is None:
			return

		starrer = channel.guild.get_member(payload.user_id)
		if starrer is None or starrer.bot:
			return

		# run checks
		fake_ctx = FakeContext(guild=channel.guild, author=starrer, channel=channel)

		if not await self.bot.blacklist(fake_ctx):
			return

		try:
			message = await channel.fetch_message(payload.message_id)
		except discord.HTTPException:
			return

		# pass event down to event_meta which handles the event but with actual discord models
		# splitting this here has the added bonus of just being able to call event_meta in
		# our command variants .star and .unstar
		try:
			await self._on_star_event_meta(event, message, starrer)
		except commands.CommandError:
			# I've decided to suppress errors here. in order to see why a star fails it has to be invoked
			# through the .star command
			return

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self._on_star_event(payload, self._on_star)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self._on_star_event(payload, self._on_unstar)

	@commands.Cog.listener()
	async def on_raw_message_delete(self, payload):
		sc = await self.config.get_entry(payload.guild_id, construct=False)

		# don't do anything if starboard is not set up, or locked
		if sc is None or sc.locked:
			return

		# see if the deleted message is stored in the database as a starred message
		row = await self.db.fetchrow(
			'SELECT * FROM star_msg WHERE message_id=$1 OR star_message_id=$1',
			payload.message_id
		)

		if row is None:
			return

		# delete starrers
		await self.db.execute('DELETE from starrers WHERE star_id=$1', row.get('id'))

		# delete from db
		await self.db.execute('DELETE FROM star_msg WHERE id=$1', row.get('id'))

		# if the deleted message was the starboard message, stop here
		if payload.message_id == row.get('star_message_id'):
			return

		# if the deleted message was the original message, we should remove the starred message
		# from the starboard

		guild = self.bot.get_guild(payload.guild_id)
		if guild is None:
			return

		try:
			star_channel = await self._get_star_channel(guild)
		except commands.CommandError:
			return

		try:
			star_message = await star_channel.fetch_message(row.get('star_message_id'))
		except discord.HTTPException:
			return

		try:
			await star_message.delete()
		except discord.HTTPException:
			return

	@commands.Cog.listener()
	async def on_raw_bulk_message_delete(self, payload):
		sc = await self.config.get_entry(payload.guild_id, construct=False)

		if sc is None or sc.locked:
			return

		sms = await self.db.fetch(
			'SELECT * FROM star_msg WHERE message_id=ANY($1::bigint[]) OR star_message_id=ANY($1::bigint[])',
			payload.message_ids
		)

		if not sms:
			return

		# if any of the bulk deleted message is stored as a star message, get their IDs
		ids = list(sm.get('id') for sm in sms)

		# delete from db
		await self.db.execute('DELETE FROM starrers WHERE star_id=ANY($1::bigint[])', ids)
		await self.db.execute('DELETE FROM star_msg WHERE id=ANY($1::bigint[])', ids)

		guild = self.bot.get_guild(payload.guild_id)
		if guild is None:
			return

		try:
			star_channel = await self._get_star_channel(guild)
		except commands.CommandError:
			return

		# fetch all the starboard messages from the related deleted messages
		to_delete = list()
		for sm in sms:
			try:
				message = await star_channel.fetch_message(sm.get('star_message_id'))
			except discord.HTTPException:
				continue

			to_delete.append(message)

		# bulk delete the starboard messages
		try:
			await star_channel.delete_messages(to_delete)
		except discord.HTTPException:
			pass

	async def _get_star_channel(self, guild):
		sc = await self.config.get_entry(guild.id, construct=False)

		if sc is None or sc.channel_id is None:
			raise SB_NOT_SET_ERROR

		star_channel = guild.get_channel(sc.channel_id)
		if star_channel is None:
			raise SB_NOT_FOUND_ERROR

		return star_channel

	async def update_star_count(self, message_id, star_message, stars):
		if not len(star_message.embeds):
			return

		embed = star_message.embeds[0]
		embed.colour = self.star_gradient_colour(stars)
		await star_message.edit(content=self.get_header(message_id, stars), embed=embed)

	def get_header(self, message_id, stars):
		return f'{self.star_emoji(stars)} **{stars}**  `ID: {message_id}`'

	def get_embed(self, message, stars):
		'''
		Stolen from Rapptz with minor tweaks, thanks!
		https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stars.py#L168-L193
		'''

		embed = discord.Embed(description=message.content)

		embed.description += '{}[Click for context!]({})'.format(
			'\n\n' if len(embed.description) else '', message.jump_url
		)

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
		)

		embed.set_footer(text='#' + message.channel.name)
		embed.timestamp = message.created_at
		embed.colour = self.star_gradient_colour(stars)

		return embed

	def star_emoji(self, stars):
		if stars >= 16:
			return '\N{SPARKLES}'
		elif stars >= 8:
			return '\N{DIZZY SYMBOL}'
		elif stars >= 4:
			return '\N{GLOWING STAR}'
		else:
			return '\N{WHITE MEDIUM STAR}'

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


def setup(bot):
	bot.add_cog(Starboard(bot))
