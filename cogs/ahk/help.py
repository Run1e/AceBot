import logging
from asyncio import sleep
from datetime import datetime, timedelta
from json import dumps, loads, JSONDecodeError

import discord
from discord.ext import commands, tasks

from cogs.mixins import AceMixin
from ids import ACTIVE_CATEGORY_ID, AHK_GUILD_ID, CLOSED_CATEGORY_ID, IGNORE_ACTIVE_CHAN_IDS, OPEN_CATEGORY_ID
from utils.context import is_mod
from utils.string import po
from utils.time import pretty_timedelta

OPEN_CHANNEL_COUNT = 3
MINIMUM_CLAIM_INTERVAL = timedelta(minutes=5)
FREE_AFTER = timedelta(minutes=30)
MINIMUM_LEASE = timedelta(minutes=2)
CHECK_FREE_EVERY = dict(seconds=80)
NEW_EMOJI = '\N{Heavy Exclamation Mark Symbol}'

OPEN_MESSAGE = (
	'This help channel is now **open**, and you can claim it by simply asking a question in it.\n\n'
	'After sending your question, the channel is moved to the\n`⏳ Help: Occupied` category, where someone will hopefully help you with your question. '
	'The channel is closed after 30 minutes of inactivity.'
)

CLOSED_MESSAGE = (
	'This channel is currently **closed**. '
	'It is not possible to send messages in it until it enters rotation again and is available under the `✅ Help: Open For Claiming` category.\n\n'
	'If your question didn\'t get answered, you can claim a new channel.'
)

log = logging.getLogger(__name__)


class AutoHotkeyHelpSystem(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.claimed_channel = self._load_claims()
		self.claimed_at = dict()

		self.channel_reclaimer.start()

		self.open_category = bot.get_channel(OPEN_CATEGORY_ID)
		self.active_category = bot.get_channel(ACTIVE_CATEGORY_ID)
		self.closed_category = bot.get_channel(CLOSED_CATEGORY_ID)

	async def cog_check(self, ctx):
		return ctx.guild.id == AHK_GUILD_ID

	def _load_claims(self):
		try:
			with open('data/claims.json', 'r') as f:
				d = loads(f.read())
				if not isinstance(d, dict):
					return dict()
				return {int(k): int(v) for k, v in d.items()}
		except (FileNotFoundError, JSONDecodeError):
			return dict()

	def _store_claims(self):
		with open('data/claims.json', 'w') as f:
			f.write(dumps(self.claimed_channel))

	@tasks.loop(**CHECK_FREE_EVERY)
	async def channel_reclaimer(self):
		on_age = datetime.utcnow() - FREE_AFTER

		for channel in self.active_category.text_channels:
			if channel.id in IGNORE_ACTIVE_CHAN_IDS:
				continue

			last_message = await self.get_last_message(channel)

			# if get_last_message failed there's likely literally no messages in the channel
			last_message_at = None if last_message is None else last_message.created_at

			claimed_at = None
			for author_id, channel_id in self.claimed_channel.items():
				if channel_id == channel.id:
					claimed_at = self.claimed_at.get(author_id, None)
					break

			pivot = max(dt for dt in (last_message_at, claimed_at) if dt is not None)

			if pivot < on_age:
				await self.close_channel(channel)

	@commands.command(hidden=True)
	@is_mod()
	async def open(self, ctx, channel: discord.TextChannel):
		'''Open a help channel.'''

		if channel.category != self.closed_category:
			raise commands.CommandError('Channel is not in the closed category.')

		await self.open_channel(channel)
		await ctx.send(f'{channel.mention} opened.')

	@commands.command(hidden=True)
	async def close(self, ctx):
		'''Releases a help channel, and moves it back into the pool of closed help channels.'''

		if ctx.channel.category != self.active_category:
			return

		is_mod = await ctx.is_mod()
		claimed_channel_id = self.claimed_channel.get(ctx.author.id, None)
		claimed_at = self.claimed_at.get(ctx.author.id, None)

		if is_mod or claimed_channel_id == ctx.channel.id:
			if is_mod:
				log.info('%s force-closing closing %s', po(ctx.author), po(ctx.channel))
			elif claimed_at is not None and claimed_at > datetime.utcnow() - MINIMUM_LEASE:
				raise commands.CommandError(f'Please wait at least {pretty_timedelta(MINIMUM_LEASE)} after claiming before closing a help channel.')

			await self.close_channel(ctx.channel)
		else:
			raise commands.CommandError('You can\'t do that.')

	async def position_channel(self, channel: discord.TextChannel, category: discord.CategoryChannel, position: int, lock_permissions: bool = True):
		channels = [c for c in category.channels]

		if channel in channels:
			channels.remove(channel)

		if position == -1:
			channels.append(channel)
		elif position < len(channels):
			channels.insert(position, channel)
		else:
			channels.append(channel)

		payload = list()

		placed_at = None
		for index, c in enumerate(channels):
			d = dict(id=c.id, position=index)
			if c == channel:
				d.update(parent_id=category.id, lock_permissions=lock_permissions)
				placed_at = index
			payload.append(d)

		log.info(f'Positioning channel #{channel} at pos {placed_at} in category {category}')

		await self.bot.http.bulk_channel_update(channel.guild.id, payload)
		channel.position = position
		channel.category_id = category.id

	async def open_channel(self, channel: discord.TextChannel):
		'''Move a channel from dormant to open.'''

		await self.position_channel(channel, self.open_category, -1)
		await self.post_message(channel, OPEN_MESSAGE, color=discord.Color.green())

	def should_open(self):
		return len(self.open_category.text_channels) < OPEN_CHANNEL_COUNT

	async def close_channel(self, channel: discord.TextChannel):
		'''Release a claimed channel from a member, making it closed.'''

		log.info(f'Attempting closing routine for #{channel}')

		owner_id = None

		for channel_owner_id, channel_id in self.claimed_channel.items():
			if channel_id == channel.id:
				owner_id = channel_owner_id
				break

		if owner_id is not None:
			val = self.claimed_channel.pop(owner_id, None)
			log.info(f'Found claimant id ({owner_id} - {channel.guild.get_member(owner_id)}), popped with value {val} - {channel.guild.get_channel(val)}')
		else:
			log.info('Could not find claimant ID in claimed_channel dict!')

		self._store_claims()

		log.info('Reclaiming %s from user id %s', po(channel), owner_id or 'UNKNOWN')

		if self.should_open():
			log.info('Opening claimed channel instead of closing, because open category needs channels.')
			await self.open_channel(channel)
		else:
			log.info('Closing claimed channel')
			await self.position_channel(channel, self.closed_category, 0)
			await channel.send(embed=discord.Embed(description=CLOSED_MESSAGE, color=discord.Color.red()))

		if self.has_postfix(channel):
			# I hate this but whatever.
			log.info(f'Claimed channel has postfix... current category: {channel.category}')
			await sleep(2.0)
			while channel.category_id == ACTIVE_CATEGORY_ID:
				await sleep(2.0)

			await self.strip_postfix(channel)
			log.info(f'Postfix stripped from #{channel}')

	async def on_open_message(self, message):
		author = message.author
		channel = message.channel

		log.info(f'New message in open category: {message.author} - #{message.channel}')

		# check whether author already has a claimed channel
		claimed_id = self.claimed_channel.get(author.id, None)
		if claimed_id is not None:  # and False:
			log.info(f'User has already claimed #{message.guild.get_channel(claimed_id)}')
			await self.post_error(message, f'You have already claimed <#{claimed_id}>, please ask your question there.')
			return

		now = datetime.utcnow()

		# check whether author has claimed another channel within the last MINIMUM_CLAIM_INTERVAL time
		last_claim_at = self.claimed_at.get(author.id, None)
		if last_claim_at is not None and last_claim_at > now - MINIMUM_CLAIM_INTERVAL:  # and False:
			log.info(f'User previously claimed a channel {pretty_timedelta(now - last_claim_at)}')
			await self.post_error(message, f'Please wait at least {pretty_timedelta(MINIMUM_CLAIM_INTERVAL)} between each help channel claim.')
			return

		if self.is_claimed(channel.id):
			log.info('Channel is already claimed (in the claimed category?)')
			return

		log.info('%s claiming %s', po(author), po(channel))

		# move channel
		try:
			await self.position_channel(channel, self.active_category, 1)
		except discord.HTTPException as exc:
			log.warning('Failed moving %s to claimed category: %s', po(channel), str(exc))
			return

		if not self.has_postfix(channel):
			try:
				log.info('Adding postfix...')
				await channel.edit(name=channel.name + '-' + NEW_EMOJI)
			except discord.HTTPException as e:
				log.info(f'Adding postfix failed: {e}')
				pass  # not a critical error, let it be

		log.info('Channel moved, positioned and given postfix (if applicable) - now setting metadata')

		# set some metadata
		self.claimed_channel[author.id] = channel.id
		self.claimed_at[author.id] = now

		self._store_claims()

		# check whether we need to move any open channels

		try:
			channel = self.closed_category.text_channels[-1]
		except IndexError:
			log.warning('No more openable channels in closed pool!')
		else:
			log.info(f'Opening new channel after claim: {channel}')
			await self.open_channel(channel)

	async def on_active_message(self, message):
		if message.content.startswith('.close'):
			log.info('Message in active channel started with .close, not processing')
			return

		channel = message.channel
		has_postfix = self.has_postfix(channel)

		if not has_postfix:
			return

		author_claimed_id = self.claimed_channel.get(message.author.id, None)
		if author_claimed_id is None or author_claimed_id != channel.id:
			await self.strip_postfix(channel)

	@commands.Cog.listener()
	async def on_message(self, message):
		guild = message.guild

		if guild is None or guild.id != AHK_GUILD_ID:
			return

		if message.author.bot:
			return

		category: discord.CategoryChannel = message.channel.category

		if category is None:
			return

		if category == self.open_category:
			await self.on_open_message(message)
		elif category == self.active_category:
			await self.on_active_message(message)

	async def post_message(self, channel: discord.TextChannel, content: str, color=None):
		last_message = await self.get_last_message(channel)

		opt = dict(description=content)
		if color is not None:
			opt['color'] = color

		e = discord.Embed(**opt)

		do_edit = last_message is not None and last_message.author == channel.guild.me and len(last_message.embeds)

		if do_edit:
			await last_message.edit(embed=e)
		else:
			await channel.send(embed=e)

	async def post_error(self, message: discord.Message, content: str):
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
			except discord.NotFound:
				pass

		if last_message is None:
			try:
				last_message = await channel.history(limit=1).flatten()
				if last_message:
					last_message = last_message[0]
				else:
					last_message = None
			except discord.HTTPException:
				pass

		return last_message

	def has_postfix(self, channel: discord.TextChannel):
		return channel.name.endswith(f'-{NEW_EMOJI}')

	def _stripped_name(self, channel: discord.TextChannel):
		return channel.name[:-2]

	async def strip_postfix(self, channel: discord.TextChannel):
		new_name = self._stripped_name(channel)
		try:
			await channel.edit(name=new_name)
		except discord.HTTPException as exc:
			log.warning(f'Failed changing name of {channel} to {new_name}: {exc}')
			pass

	def is_claimed(self, channel_id):
		return channel_id in self.claimed_channel.values()


def setup(bot):
	bot.add_cog(AutoHotkeyHelpSystem(bot))
