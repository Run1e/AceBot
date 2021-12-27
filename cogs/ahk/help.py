import asyncio
import logging
from asyncio import create_task, gather, sleep
from datetime import timedelta
from enum import Enum

import aiohttp
import disnake
from disnake.ext import commands, tasks

from cogs.mixins import AceMixin
from cogs.mod import Severity
from config import GAME_PRED_URL, HELP_CONTROLLERS
from ids import (
	GET_HELP_CHAN_ID, RULES_CHAN_ID
)
from utils.string import po
from utils.time import pretty_timedelta

log = logging.getLogger(__name__)

OPEN_CHANNEL_COUNT = 2
MINIMUM_CLAIM_INTERVAL = timedelta(minutes=5)
FREE_AFTER = timedelta(minutes=1)
MINIMUM_LEASE = timedelta(minutes=2)
CHECK_FREE_EVERY = dict(seconds=10)
NEW_EMOJI = '\N{Heavy Exclamation Mark Symbol}'

OPEN_MESSAGE = (
	'This help channel is now **open**, and you can claim it by simply asking a question in it.\n\n'
	'After sending your question, the channel is moved to the\n`⏳ Help: Occupied` category, where someone will hopefully help you with your question. '
	'The channel is closed after 30 minutes of inactivity.'
)

CLOSED_MESSAGE = (
	'This channel is currently **closed**. '
	'It is not possible to send messages in it until it enters rotation again and is available under the `✅ Help: Ask Here` category.\n\n'
	'If your question didn\'t get answered, you can claim a new channel.'
)


class ChannelState(Enum):
	OPENING = 1
	ACTIVATING = 2
	CLOSING = 3


class StateClearer:
	def __init__(self, clear_fn, channel):
		self.clear_fn = clear_fn
		self.channel = channel

	def __enter__(self):
		pass

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.clear_fn(self.channel)


class Controller:
	def __init__(self, bot, guild_id, open_category_id, active_category_id, closed_category_id, ignore_channel_ids):
		self.bot = bot

		self.lock = asyncio.Lock()

		self.guild_id = guild_id

		self._messages = {}
		self._states = dict()  # channel_id: ChannelState
		self._claimed_at = dict()  # user_id: datetime

		self.ignored = ignore_channel_ids
		self._open_category_id = open_category_id
		self._active_category_id = active_category_id
		self._closed_category_id = closed_category_id

	@property
	def guild(self):
		return self.bot.get_guild(self.guild_id)

	@property
	def open_category(self):
		return self.bot.get_channel(self._open_category_id)

	@property
	def active_category(self):
		return self.bot.get_channel(self._active_category_id)

	@property
	def closed_category(self):
		return self.bot.get_channel(self._closed_category_id)

	def _get_channels(self, category: disnake.CategoryChannel, state: ChannelState):
		"""
		Get a list of the channels in the category, but:
		1. without ignored channels (set in config.py)
		2. without channels that are currently being moved out of the category (by having a state in ._state)
		3. if forecast=True in the calling function, state will be None, and channels that are-
			about to be moved in are also not included. if =True, they are
		"""

		cached = []
		ignored = set(self.ignored)

		for channel_id, channel_state in self._states.items():
			if channel_state is state:
				cached.append(self.bot.get_channel(channel_id))
			else:
				ignored.add(channel_id)

		for channel in category.text_channels:
			if channel.id not in ignored:
				cached.append(channel)

		return list(sorted(set(cached), key=lambda c: c.position))

	def open_channels(self, forecast=True):
		return self._get_channels(self.open_category, ChannelState.OPENING if forecast else None)

	def active_channels(self, forecast=True):
		return self._get_channels(self.active_category, ChannelState.ACTIVATING if forecast else None)

	def closed_channels(self, forecast=True):
		return self._get_channels(self.closed_category, ChannelState.CLOSING if forecast else None)

	def get_bottom_pos(self):
		return max(channel.position for channel in self.guild.text_channels) + 1

	def get_state(self, channel):
		return self._states.get(channel.id, None)

	def set_state(self, channel, state):
		log.info('%s is now %s', channel, state)
		self._states[channel.id] = state

	def clear_state(self, channel):
		log.info('%s now has no state', channel)
		self._states.pop(channel.id, None)

	async def has_channel(self, user_id):
		channel_id = await self.bot.db.fetchval(
			'SELECT channel_id FROM help_claim WHERE guild_id=$1 AND user_id=$2',
			self.guild.id, user_id
		)

		if channel_id and any(channel.id == channel_id for channel in self.active_channels()):
			return channel_id

		return None

	async def get_claimant(self, channel_id):
		return await self.bot.db.fetchval(
			'SELECT user_id FROM help_claim WHERE guild_id=$1 AND channel_id=$2',
			self.guild.id, channel_id
		)

	async def set_claimant(self, channel_id, user_id):
		async with self.bot.db.acquire() as connection:
			async with connection.transaction():
				await connection.execute(
					'DELETE FROM help_claim WHERE guild_id=$1 AND user_id=$2',
					self.guild.id, user_id
				)

				await connection.execute(
					'INSERT INTO help_claim VALUES ($1, $2, $3) ON CONFLICT (guild_id, channel_id) DO UPDATE SET user_id=$3',
					self.guild.id, channel_id, user_id
				)

	async def clear_claimant(self, channel_id):
		await self.bot.db.execute(
			'DELETE FROM help_claim WHERE guild_id=$1 AND channel_id=$2',
			self.guild.id, channel_id
		)

	@tasks.loop(**CHECK_FREE_EVERY)
	async def reclaimer(self):
		on_age = disnake.utils.utcnow() - FREE_AFTER

		for channel in self.active_channels(forecast=False):
			last_message = await self.get_last_message(channel)

			# if get_last_message failed there's likely literally no messages in the channel
			last_message_at = None if last_message is None else last_message.created_at

			claimed_at = self._claimed_at.get(channel.id, None)

			if last_message_at is None and claimed_at is None:
				continue

			pivot = max(dt for dt in (last_message_at, claimed_at) if dt is not None)

			if pivot < on_age:
				self.set_state(channel, ChannelState.CLOSING)
				await self.close_channel(channel)

	async def process_message(self, message):
		channel: disnake.TextChannel = message.channel

		# has to be in a category
		category: disnake.CategoryChannel = channel.category
		if category is None:
			return

		# ignore messages in ignored channels
		if channel.id in self.ignored:
			return

		async with self.lock:
			# ignore channels currently being processed elsewhere (by having a state)
			channel_state = self.get_state(channel)
			if channel_state is not None:
				log.info('Ignoring channel %s because of its state: %s', channel.name, channel_state)
				return

			if category == self.open_category:
				await self.on_open_message(message)
			elif category == self.active_category:
				await self.on_active_message(message)

	async def on_open_message(self, message: disnake.Message):
		claimed_id = await self.has_channel(message.author.id)
		if claimed_id is not None:
			log.info(f'User has already claimed #{message.guild.get_channel(claimed_id)}')
			await self.post_error(message, f'You have already claimed <#{claimed_id}>, please ask your question there.')
			return

		now = disnake.utils.utcnow()
		author: disnake.Member = message.author

		# check whether author has claimed another channel within the last MINIMUM_CLAIM_INTERVAL time
		last_claim_at = self._claimed_at.get(author.id, None)
		if last_claim_at is not None and last_claim_at > now - MINIMUM_CLAIM_INTERVAL:  # and False:
			log.info(f'User previously claimed a channel {pretty_timedelta(now - last_claim_at)} ago')
			await self.post_error(message, f'Please wait at least {pretty_timedelta(MINIMUM_CLAIM_INTERVAL)} between each help channel claim.')
			return

		channel: disnake.TextChannel = message.channel

		log.info('%s claiming %s', po(author), po(channel))

		# activate the channel
		self.set_state(channel, ChannelState.ACTIVATING)
		await self.set_claimant(channel.id, message.author.id)
		create_task(self.activate_channel(message))

		# maybe open new channel

		if len(self.open_channels(forecast=True)) >= OPEN_CHANNEL_COUNT:
			log.info('No need to open another channel')
			return

		closed_channels = self.closed_channels(forecast=False)
		if not closed_channels:
			log.info('No closed channels available to move to open category!')
			return

		to_open = closed_channels[0]

		self.set_state(to_open, ChannelState.OPENING)
		create_task(self.open_channel(to_open))

	# print('open message', self.open_channels)

	async def on_active_message(self, message):
		if message.content.startswith('.close'):
			return

		channel = message.channel

		claimant_id = await self.get_claimant(channel.id)

		if claimant_id is not None and claimant_id == message.author.id:
			msgs = self._messages.get(channel.id, None)

			# nothing there, skip for now
			if msgs is None:
				return

			msgs.append(message)

			create_task(self.maybe_yell(msgs))
		else:
			# clear claimed_messages if someone else is talking now
			self._messages.pop(channel.id, None)

			# remove postfix if it's there
			if self.has_postfix(channel):
				await channel._state.http.edit_channel(channel.id, name=self.without_postfix(channel))

	async def move(self, channel: disnake.TextChannel, parent_id, reason=None):
		with StateClearer(self.clear_state, channel):
			try:
				await channel._move(
					self.get_bottom_pos(),
					parent_id=parent_id,
					lock_permissions=True,
					reason=reason
				)
			except (disnake.HTTPException, asyncio.CancelledError):
				return False

		return True

	async def open_channel(self, channel: disnake.TextChannel):
		result = await self.move(
			channel,
			parent_id=self.open_category.id,
		)

		if not result:
			return

		await self.post_message(channel, OPEN_MESSAGE, color=disnake.Color.green())

	async def activate_channel(self, message: disnake.Message):
		channel: disnake.Channel = message.channel

		result = await self.move(channel, parent_id=self.active_category.id)

		if not result:
			await self.clear_claimant(channel.id)
			return

		# set some metadata
		self._claimed_at[channel.id] = disnake.utils.utcnow()

		data = dict(topic=message.jump_url)

		if not self.has_postfix(channel):
			data['name'] = self.with_postfix(channel)

		msgs = [message]
		self._messages[channel.id] = msgs

		await asyncio.gather(
			self.maybe_yell(msgs),
			channel._state.http.edit_channel(channel.id, **data),
			return_exceptions=True
		)

	async def close_channel(self, channel: disnake.TextChannel):
		result = await self.move(
			channel,
			parent_id=self.closed_category.id,
		)

		if not result:
			return

		await self.clear_claimant(channel.id)
		self._messages.pop(channel.id, None)

		data = dict(topic=f'<#{GET_HELP_CHAN_ID}>')

		if self.has_postfix(channel):
			data['name'] = self.without_postfix(channel)

		await gather(
			channel._state.http.edit_channel(channel.id, **data),
			self.post_message(channel, CLOSED_MESSAGE, color=disnake.Color.red()),
			return_exceptions=True
		)

	async def post_message(self, channel: disnake.TextChannel, content: str, color=None):
		last_message = await self.get_last_message(channel)

		opt = dict(description=content)
		if color is not None:
			opt['color'] = color

		e = disnake.Embed(**opt)

		is_my_embed = last_message is not None and last_message.author == channel.guild.me and len(last_message.embeds)
		do_edit = is_my_embed and last_message.embeds[0].description in (OPEN_MESSAGE, CLOSED_MESSAGE)

		if do_edit:
			await last_message.edit(content=None, embed=e)
		else:
			await channel.send(embed=e)

	async def post_error(self, message: disnake.Message, content: str):
		await message.delete()
		await message.channel.send(f'{message.author.mention} {content}', delete_after=10)

	async def get_last_message(self, channel):
		last_message = channel.last_message
		if last_message is not None:
			return last_message

		last_message_id = channel.last_message_id
		if last_message_id is not None:
			try:
				last_message = await channel.fetch_message(channel.last_message_id)
			except disnake.NotFound:
				pass

		if last_message is None:
			try:
				last_message = await channel.history(limit=1).flatten()
				if last_message:
					last_message = last_message[0]
				else:
					last_message = None
			except disnake.HTTPException:
				pass

		return last_message

	def has_postfix(self, channel: disnake.TextChannel):
		return channel.name.endswith(f'-{NEW_EMOJI}')

	def with_postfix(self, channel: disnake.TextChannel):
		return f'{channel.name}-{NEW_EMOJI}'

	def without_postfix(self, channel: disnake.TextChannel):
		return channel.name[:-2]

	async def classify(self, text):
		try:
			async with self.bot.aiohttp.post(GAME_PRED_URL, data=dict(q=text)) as resp:
				if resp.status != 200:
					return 0.0

				json = await resp.json()
				return json['p']
		except aiohttp.ClientError:
			return 0.0

	def _make_yell_embed(self, score):
		s = (
			'Your scripting question looks like it might be about a game, which is not allowed here. '
			f'Please make sure you are familiar with the <#{RULES_CHAN_ID}>, specifically rule 5.\n\n'
			'If your question does not break the rules, you can safely ignore this message. '
			'If you continue and your question is later found to break the rules, you might risk a ban.'
		)

		e = disnake.Embed(
			title='Hi there!',
			description=s,
			color=disnake.Color.orange()
		)

		e.set_footer(text=f'This message was sent by an automated system (confidence: {int(score * 100)}%)')

		return e

	async def maybe_yell(self, msgs):
		channel = msgs[0].channel
		author = msgs[0].author
		content = ' '.join(m.content for m in msgs)

		pivot = 0.65
		c = await self.classify(content)

		if c >= pivot:
			# wait a bit so it's not so confusing when the channel is grabbed
			await sleep(2.0)

			await channel.send(
				content=author.mention,
				embed=self._make_yell_embed(c)
			)

			self.bot.dispatch(
				'log', channel.guild, author, action='GAME SCRIPT PREDICTION',
				severity=Severity.LOW, message=msgs[0], reason=f'Model class prediction {c:.2f} with pivot {pivot:.2f}'
			)

			self._messages.pop(channel.id, None)


class HelpSystem(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.controllers = {
			guild_id: Controller(bot, guild_id, **config_dict)
			for guild_id, config_dict in HELP_CONTROLLERS.items()
		}

		create_task(self.start_reclaimers())

	@commands.Cog.listener()
	async def on_message(self, message):
		await self.bot.wait_until_ready()

		if message.guild is None:
			return

		if message.author.bot:
			return

		controller = self.controllers.get(message.guild.id, None)

		if controller:
			await controller.process_message(message)

	@commands.command(hidden=True)
	async def ask(self, ctx):
		'''Responds with the currently open for claiming channels.'''

		controller: Controller = self.controllers.get(ctx.message.guild.id, None)
		if not controller:
			return

		channels = controller.open_channels(forecast=False)

		if not channels:
			raise commands.CommandError('No help channels are currently open for claiming. Please wait for a channel to become available.')

		mentions = [c.mention for c in channels]
		mention_count = len(mentions)

		if mention_count < 3:
			ment = ' and '.join(mentions)
		else:
			mentions[-1] = 'and ' + mentions[-1]
			ment = ', '.join(mentions)

		text = (
			'If you\'re looking for scripting help you should ask in an open help channel.\n\n'
			'The currently available help channels are {0}.'
		).format(ment)

		await ctx.send(text)

	@commands.command()
	async def close(self, ctx):
		controller: Controller = self.controllers.get(ctx.message.guild.id, None)
		if not controller:
			return

		# check that this is a channel in an active category that can actually be closed
		if ctx.channel.category != controller.active_category:
			return

		is_mod = await ctx.is_mod()
		channel_claimant_id = await controller.get_claimant(ctx.channel.id)

		if not is_mod and channel_claimant_id != ctx.author.id:
			raise commands.CommandError('You can\'t do that.')

		log.info('%s is closing %s', po(ctx.author), po(ctx.channel))

		await controller.close_channel(ctx.channel)

	async def start_reclaimers(self):
		await self.bot.wait_until_ready()

		for controller in self.controllers.values():
			controller.reclaimer.start()


def setup(bot):
	bot.add_cog(HelpSystem(bot))
