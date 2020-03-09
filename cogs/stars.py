import discord
import logging

from discord.ext import commands, tasks
from datetime import datetime, timedelta
from asyncpg.exceptions import UniqueViolationError

from utils.context import is_mod
from utils.configtable import ConfigTable, ConfigTableRecord
from utils.context import can_prompt
from cogs.mixins import AceMixin

log = logging.getLogger(__name__)
STAR_EMOJI = '\N{WHITE MEDIUM STAR}'
STAR_COOLDOWN = timedelta(minutes=3)
STAR_CUTOFF = timedelta(days=7)

SB_NOT_EXIST_ERROR = commands.CommandError('Please set up a starboard using `star create` first.')
SB_NOT_SET_ERROR = commands.CommandError('No starboard channel has been set yet.')
SB_NOT_FOUND_ERROR = commands.CommandError('Starboard channel set but not found. Please create a new one.')
SB_LOCKED_ERROR = commands.CommandError('Starboard has been locked and can not be used at the moment.')
SB_ORIG_MSG_NOT_FOUND_ERROR = commands.CommandError('Could not find original message.')
SB_STAR_MSG_NOT_FOUND_ERROR = commands.CommandError('Could not find starred message.')


class StarboardConfigRecord(ConfigTableRecord):

	@property
	def channel(self):
		if self.channel_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)
		if guild is None:
			return None

		return guild.get_channel(self.channel_id)


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

	@tasks.loop(minutes=20)
	async def purger(self):
		'''Purges old and underperforming stars depending on guild starboard settings.'''

		boards = await self.db.fetch(
			'SELECT guild_id, channel_id, threshold FROM starboard WHERE locked IS FALSE AND threshold IS NOT NULL'
		)

		pivot = datetime.utcnow() - STAR_CUTOFF
		to_delete = list()

		for board in boards:
			rows = await self.db.fetch(
				self.purge_query, board.get('guild_id'), pivot, board.get('threshold') - 1
			)

			if not rows:
				continue

			star_channel = self.bot.get_channel(board.get('channel_id'))
			if star_channel is None:
				continue

			for row in rows:
				to_delete.append(row.get('id'))

				try:
					star_message = await star_channel.fetch_message(row.get('star_message_id'))
					await star_message.delete()
				except discord.HTTPException:
					continue

		if to_delete:
			await self.db.execute('DELETE FROM star_msg WHERE id=ANY($1::bigint[])', to_delete)

	async def get_board(self, guild_id, raise_on_locked=True):
		board = await self.config.get_entry(guild_id, construct=False)

		if board is None:
			raise SB_NOT_EXIST_ERROR

		if raise_on_locked and board.locked:
			raise SB_LOCKED_ERROR

		return board

	@commands.group(name='star', invoke_without_command=True)
	@commands.bot_has_permissions(embed_links=True, add_reactions=True)
	async def _star(self, ctx, *, message_id: discord.Message = None):
		'''Star a message by ID.'''

		if message_id is None:
			await ctx.send_help(self._star)
			return

		board = await self.get_board(ctx.guild.id)
		await self._on_star_event_meta(self._on_star, board, message_id, ctx.author)
		await ctx.send('Starred!')

	@commands.command()
	@commands.bot_has_permissions(embed_links=True, add_reactions=True)
	async def unstar(self, ctx, *, message_id: discord.Message):
		'''Unstar a message by ID.'''

		board = await self.get_board(ctx.guild.id)
		await self._on_star_event_meta(self._on_unstar, board, message_id, ctx.author)
		await ctx.send('Unstarred.')

	@_star.command()
	@is_mod()
	@can_prompt()
	@commands.bot_has_permissions(manage_channels=True, manage_roles=True)
	async def create(self, ctx):
		'''Creates a new starboard.'''

		board = await self.config.get_entry(ctx.guild.id)

		if board.channel is not None:
			raise commands.CommandError('Starboard already exists: {}'.format(board.channel.mention))

		if board.channel_id is not None:
			prompt = (
				'Do you want to create a new one?\n\n'
				'NOTE: This will delete all data related to previously starred messages. If you\'re unsure '
				'what to do, join the AceBot support server by aborting this prompt and typing '
				'`{}support`'.format(ctx.prefix)
			)

			result = await ctx.prompt(title='The previous starboard seems to have been deleted.', prompt=prompt)

			if not result:
				raise commands.CommandError('Aborted starboard creation.')

		await self.db.execute('DELETE FROM star_msg WHERE guild_id=$1', ctx.guild.id)

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

		topic = (
			'Star a message by adding a :star: reaction to it! Do "help star" to see all starboard related commands.'
		)

		try:
			channel = await ctx.guild.create_text_channel(
				name='starboard', overwrites=overwrites, reason=reason, topic=topic
			)
		except discord.HTTPException:
			raise commands.CommandError('An unexpected error happened when creating the starboard channel.')

		await board.update(channel_id=channel.id)

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

				if user.id == row.get('user_id'):
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
	@can_prompt()
	@commands.bot_has_permissions(manage_messages=True)
	async def delete(self, ctx, *, message_id: StarConverter):
		'''Remove a starred message. The author, starrer or any moderator can use this on any given starred message.'''

		row = message_id

		# see if invoker is either original starrer, or author of original message
		if ctx.author.id not in (row.get('user_id'), row.get('starrer_id')):

			# if not, check if invoker is moderator
			if not await ctx.is_mod():
				# if not, raise
				raise commands.CommandError(
					'Only moderators, the original starrer or the original messages author '
					'can remove this starred message.'
				)

			# if invoker is moderator, run the admin prompter
			await ctx.admin_prompt(raise_on_abort=True)

		await self.db.execute('DELETE FROM star_msg WHERE id=$1', row.get('id'))

		try:
			star_channel = await self._get_star_channel(ctx.guild)
			star_message = await star_channel.fetch_message(row.get('star_message_id'))
			await star_message.delete()
		except (discord.HTTPException, commands.CommandError):
			pass

		await ctx.send('Star deleted.')

	@_star.command()
	@is_mod()
	async def threshold(self, ctx, threshold: int = None):
		'''Starred messages with fewer than `threshold` stars will be removed from the starboard after a week has passed. To disable auto-cleaning completely, leave argument blank.'''

		board = await self.get_board(ctx.guild.id)

		if threshold is None:
			if board.threshold is None:
				raise commands.CommandError('Auto-cleaning is already disabled.')
			await board.update(threshold=None)
			await ctx.send('Starboard auto-cleaning disabled.')
		else:
			if not 0 < threshold < 32767:
				raise commands.CommandError('Auto-clean star threshold has to be between 0 and 32767.')

			await board.update(threshold=threshold)
			await ctx.send(
				'Starred messages with fewer than {} stars after a week will now be removed from the starboard.'.format(
					threshold
				)
			)

	@_star.command()
	@is_mod()
	async def lock(self, ctx):
		'''Lock the starboard.'''

		board = await self.get_board(ctx.guild.id, raise_on_locked=False)
		await board.update(locked=True)

		await ctx.send('Starboard locked.')

	@_star.command()
	@is_mod()
	async def unlock(self, ctx):
		'''Unlock the starboard.'''

		board = await self.get_board(ctx.guild.id, raise_on_locked=False)
		await board.update(locked=False)

		await ctx.send('Starboard unlocked.')

	async def _on_star(self, starrer, star_channel, message, star_message, record):
		if record is not None:
			# this message has been starred before.

			# original starrer can't restar
			if starrer.id == record.get('starrer_id'):
				raise commands.CommandError('Original starrer can\'t restar.')

			# author of message can't star
			if starrer.id == record.get('user_id'):
				raise commands.CommandError('Message authors can\'t star their own message.')

			try:
				await self.db.execute(
					'INSERT INTO starrers (star_id, user_id) VALUES ($1, $2)',
					record.get('id'), starrer.id
				)
			except UniqueViolationError:
				return

			starrer_count = await self.db.fetchval(
				'SELECT COUNT(*) FROM starrers WHERE star_id=$1',
				record.get('id')
			)

			await self.update_star_count(record.get('message_id'), star_message, starrer_count + 1)

		else:
			# new star. post it and store it

			if star_channel is None:
				raise commands.CommandError('I don\'t know where to post this. Try setting the starboard again.')

			# message=None happens if the message being starred originated from the starboard, this setting
			# star_message=message and message=None
			if message is None:
				raise commands.CommandError('Can\'t star messages from the starboard.')

			if message.author == starrer:
				raise commands.CommandError('Can\'t star your own message.')

			if message.channel.is_nsfw() and not star_channel.is_nsfw():
				raise commands.CommandError('Can\'t star message from nsfw channel into non-nsfw starboard.')

			if not len(message.content) and not len(message.attachments):
				raise commands.CommandError('Can\'t star this message because it has no embeddable content.')

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
				raise commands.CommandError(
					'Failed posting to starboard.\nMake sure the bot has permissions to post there.'
				)

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
				raise commands.CommandError('You have not previously starred this, or you are the original starrer.')

			# otherwise we need to update the star count
			starrer_count = await self.db.fetchval(
				'SELECT COUNT(*) FROM starrers WHERE star_id=$1',
				record.get('id')
			)

			await self.update_star_count(record.get('message_id'), star_message, starrer_count + 1)

		else:
			pass  # ???

	async def _on_star_event_meta(self, event, board, message, starrer):
		# get the starmessage record if it exists
		row = await self.db.fetchrow(
			'SELECT * FROM star_msg WHERE guild_id=$1 AND (message_id=$2 OR star_message_id=$2)',
			message.guild.id, message.id
		)

		if message.channel.id == board.channel_id:
			# if the reaction event happened in the starboard channel we already have a reference
			# to both the channel and starred message
			star_channel = message.channel
			star_message = message
			message = None
		else:

			# get the star channel. this raises commanderror on failure
			star_channel = await self._get_star_channel(message.guild, board=board)

			# we should also find the starred message
			if row is None:
				# if row is none, this is a new star - and no starred message exists
				star_message = None
			else:
				# if we have the record we catch fetch the starred message
				try:
					star_message = await star_channel.fetch_message(row.get('star_message_id'))
				except discord.HTTPException:
					raise SB_STAR_MSG_NOT_FOUND_ERROR

		# stop if attempted star is too old
		# if star_message was not found (star is new) then use the original messages timestamp
		# if a star_message *was* found, use that instead as it's the new basis of "star message age"
		if datetime.utcnow() - STAR_CUTOFF > (star_message or message).created_at:
			raise commands.CommandError('Stars can\'t be added or removed from messages older than a week.')

		# trigger event
		# message and star_message can be populated, or *one* of them can be None
		await event(starrer, star_channel, message, star_message, row)

	async def _on_star_event(self, payload, event):
		# only listen for star emojis
		if str(payload.emoji) != STAR_EMOJI:
			return

		if payload.guild_id is None:
			return

		try:
			board = await self.get_board(payload.guild_id)
		except commands.CommandError:
			return

		# attempt to get the message
		channel = self.bot.get_channel(payload.channel_id)
		if channel is None:
			return

		starrer = channel.guild.get_member(payload.user_id)
		if starrer is None or starrer.bot:
			return

		try:
			message = await channel.fetch_message(payload.message_id)
		except discord.HTTPException:
			return

		# pass event down to event_meta which handles the event but with actual discord models
		# splitting this here has the added bonus of just being able to call event_meta in
		# our command variants .star and .unstar
		try:
			await self._on_star_event_meta(event, board, message, starrer)
		except commands.CommandError:

			# remove reaction as "feedback" to starring being rejected
			# obviously, there's only a reaction to remove if this was the on_star event
			if event == self._on_star:
				try:
					await message.remove_reaction(payload.emoji, starrer)
				except discord.HTTPException:
					pass

			# I've decided to suppress errors here. in order to see why a star fails it has to be invoked
			# through the .star or .unstar commands
			return

	async def _get_star_channel(self, guild, board=None):
		if board is None:
			board = await self.get_board(guild.id, raise_on_locked=False)

		if board is None:
			raise SB_NOT_EXIST_ERROR

		if board.channel_id is None:
			raise SB_NOT_SET_ERROR

		star_channel = guild.get_channel(board.channel_id)
		if star_channel is None:
			raise SB_NOT_FOUND_ERROR

		return star_channel

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		await self._on_star_event(payload, self._on_star)

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload):
		await self._on_star_event(payload, self._on_unstar)

	@commands.Cog.listener()
	async def on_raw_message_delete(self, payload):
		board = await self.config.get_entry(payload.guild_id, construct=False)

		if board is None or board.locked:
			return

		# see if the deleted message is stored in the database as a starred message
		row = await self.db.fetchrow(
			'SELECT * FROM star_msg WHERE message_id=$1 OR star_message_id=$1',
			payload.message_id
		)

		if row is None:
			return

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
			star_channel = await self._get_star_channel(guild, board=board)
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
		board = await self.config.get_entry(payload.guild_id, construct=False)

		if board is None or board.locked:
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
		await self.db.execute('DELETE FROM star_msg WHERE id=ANY($1::bigint[])', ids)

		guild = self.bot.get_guild(payload.guild_id)
		if guild is None:
			return

		try:
			star_channel = await self._get_star_channel(guild, board=board)
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
