import logging
from asyncio import Lock
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from cogs.ahk.ids import AHK_GUILD_ID, CLAIMED_CATEGORY_ID, CLOSED_CATEGORY_ID, OPEN_CATEGORY_ID
from cogs.mixins import AceMixin
from utils.context import is_mod
from utils.string import po
from utils.time import pretty_timedelta

OPEN_CHANNEL_COUNT = 3
MINIMUM_CLAIM_INTERVAL = timedelta(seconds=60)
FREE_AFTER = timedelta(seconds=120)
CHECK_FREE_EVERY = dict(seconds=5)

OPEN_MESSAGE = (
	'This help channel is now **open**, and you can claim it by simply asking a question. '
	'After sending a message, the channel will be moved to the **HELP: CLAIMED** category, and someone will hopefully help you with your question.\n\n'
	'After 30 minutes of inactivity the channel will be moved to the **HELP: CLOSED** category. '
	'You can also close it manually by invoking the `.close` command.'
)

CLOSED_MESSAGE = (
	'This channel is currently **closed**. '
	'It is not possible to send messages in it until it enters rotation again and is available under the **HELP: OPEN** category.\n\n'
	'If your question didn\'t get answered, you can try and claim another channel under the **HELP: OPEN** category.'
)

OPEN_TOPIC = 'Claim this channel by simply sending a message with a question into it!'
CLAIMED_TOPIC = 'This channel is currently claimed by {0}'
CLOSED_TOPIC = 'This channel is currently out of rotation. It is still visible so it can be searched through.'

log = logging.getLogger(__name__)


class AutoHotkeyHelpSystem(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.claim_lock = Lock()
		self.close_lock = Lock()

		self.claimed_channel = dict()
		self.claimed_at = dict()
		self.channel_reclaimer.start()

		self.claimed_category = bot.get_channel(CLAIMED_CATEGORY_ID)
		self.closed_category = bot.get_channel(CLOSED_CATEGORY_ID)
		self.open_category = bot.get_channel(OPEN_CATEGORY_ID)

	async def cog_check(self, ctx):
		return ctx.guild.id == AHK_GUILD_ID

	@tasks.loop(**CHECK_FREE_EVERY)
	async def channel_reclaimer(self):
		on_age = datetime.utcnow() - FREE_AFTER

		for channel in self.claimed_category.text_channels:
			last_message = channel.last_message
			if last_message is None:
				try:
					last_message = await channel.fetch_message(channel.last_message_id)
				except discord.HTTPException:
					continue  # just skip it for now

			if last_message.created_at < on_age:
				await self.close_channel(channel)

	@commands.command()
	@is_mod()
	async def open(self, ctx, channel: discord.TextChannel):
		'''Open a help channel.'''

		if channel.category != self.closed_category:
			raise commands.CommandError('Channel is not in the closed category.')

		await self.open_channel(channel)
		await ctx.send(f'{channel.mention} opened.')

	@commands.command()
	async def close(self, ctx):
		'''Releases a help channel, and moves it back into the pool of available help channels.'''

		if ctx.channel.category != self.claimed_category:
			return

		is_mod = await ctx.is_mod()
		claimed_channel_id = self.claimed_channel.get(ctx.author.id, None)

		if is_mod or claimed_channel_id == ctx.channel.id:
			if is_mod:
				log.info('%s force-closing closing %s', po(ctx.author), po(ctx.channel))

			await self.close_channel(ctx.channel)
		else:
			raise commands.CommandError('You can\'t do that.')

	async def open_channel(self, channel: discord.TextChannel):
		'''Move a channel from dormant to open.'''

		if channel.category_id != OPEN_CATEGORY_ID or channel.topic != OPEN_TOPIC or not channel.permissions_synced:
			await channel.edit(category=self.open_category, topic=OPEN_TOPIC, sync_permissions=True)

		await self.post_message(channel, OPEN_MESSAGE)

	async def close_channel(self, channel: discord.TextChannel):
		'''Release a claimed channel from a member, making it closed.'''

		async with self.close_lock:
			owner_id = None

			for channel_owner_id, channel_id in self.claimed_channel.items():
				if channel_id == channel.id:
					owner_id = channel_owner_id
					break

			if owner_id is not None:
				self.claimed_channel.pop(owner_id)

			log.info('Reclaiming %s from user id %s', po(channel), owner_id or 'UNKNOWN')

			if channel.category_id != CLOSED_CATEGORY_ID or channel.topic != CLOSED_TOPIC or not channel.permissions_synced:
				await channel.edit(category=self.closed_category, topic=CLOSED_TOPIC, sync_permissions=True)

			await self.post_message(channel, CLOSED_MESSAGE)

	@commands.Cog.listener()
	async def on_message(self, message):
		guild = message.guild

		if guild is None or guild.id != AHK_GUILD_ID:
			return

		author = message.author

		if author.bot:
			return

		channel: discord.TextChannel = message.channel
		category: discord.CategoryChannel = channel.category

		if category is None or category.id != OPEN_CATEGORY_ID:
			return

		# check whether author already has a claimed channel
		claimed_id = self.claimed_channel.get(author.id, None)
		if claimed_id is not None:
			await self.post_error(message, f'You have already claimed <#{claimed_id}>, please ask your question there.')
			return

		now = datetime.utcnow()

		# check whether author has claimed another channel within the last MINIMUM_CLAIM_INTERVAL time
		last_claim_at = self.claimed_at.get(author.id, None)
		if last_claim_at is not None and last_claim_at > now - MINIMUM_CLAIM_INTERVAL:
			await self.post_error(message, f'Please wait at least {pretty_timedelta(MINIMUM_CLAIM_INTERVAL)} between each help channel claim.')
			return

		# otherwise, claim it!
		async with self.claim_lock:
			if self.is_claimed(channel.id):
				return

			log.info('%s claiming %s', po(author), po(channel))

			# find a new openable channel before doing any moving
			new_open = self.get_openable_channel()

			# move channel
			try:
				await channel.edit(category=self.claimed_category, topic=CLAIMED_TOPIC.format(author), sync_permissions=True)
			except discord.HTTPException:
				log.warning('Failed moving %s to claimed category.', po(channel))
				return

			# set some metadata
			self.claimed_channel[author.id] = channel.id
			self.claimed_at[author.id] = now

			# check whether we need to move any open channels
			await self.maybe_open(new_open)

	async def post_message(self, channel: discord.TextChannel, content: str):
		last_message = channel.last_message
		if last_message is None:
			try:
				last_message = await channel.fetch_message(channel.last_message_id)
			except discord.NotFound:
				pass

		e = discord.Embed(description=content)
		do_edit = last_message is not None and last_message.author == channel.guild.me and len(last_message.embeds)

		if do_edit:
			await last_message.edit(embed=e)
		else:
			await channel.send(embed=e)

	async def post_error(self, message: discord.Message, content: str):
		await message.delete()
		await message.channel.send(f'{message.author.mention} {content}', delete_after=10)

	def is_claimed(self, channel_id):
		return channel_id in self.claimed_channel.values()

	def get_openable_channel(self):
		try:
			return self.closed_category.text_channels[-1]
		except IndexError:
			return None

	async def maybe_open(self, channel):
		# check whether we need to move any open channels
		if len(self.open_category.text_channels) < OPEN_CHANNEL_COUNT:
			if channel is not None:
				await self.open_channel(channel)
			else:
				log.warning('No more openable channels in closed pool!')


def setup(bot):
	bot.add_cog(AutoHotkeyHelpSystem(bot))
