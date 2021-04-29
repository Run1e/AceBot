import logging

log = logging.getLogger(__name__)
import re
import string
from asyncio import Lock, sleep
from datetime import datetime, timedelta
from json import JSONDecodeError, dumps, loads

import discord
import numpy as np
import unidecode
from discord.ext import commands, tasks

log.info('Importing keras...')
from tensorflow import keras

log.info('Finished importing keras.')

from cogs.mixins import AceMixin
from ids import ACTIVE_CATEGORY_ID, ACTIVE_INFO_CHAN_ID, AHK_GUILD_ID, CLOSED_CATEGORY_ID, GET_HELP_CHAN_ID, IGNORE_ACTIVE_CHAN_IDS, OPEN_CATEGORY_ID, \
	RULES_CHAN_ID
from utils.context import is_mod
from utils.string import po
from utils.time import pretty_timedelta

from cogs.mod import Severity

# from nltk.corpus.stopwords
STOPWORDS_EN = [
	'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', "you're", "you've", "you'll", "you'd", 'your', 'yours', 'yourself',
	'yourselves', 'he', 'him', 'his', 'himself', 'she', "she's", 'her', 'hers', 'herself', 'it', "it's", 'its', 'itself', 'they', 'them', 'their',
	'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', "that'll", 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be',
	'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as',
	'until', 'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above',
	'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
	'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
	'so', 'than', 'too', 'very', 't', 'can', 'will', 'just', 'don', "don't", 'should', "should've", 'now', 'll', 'm', 'o', 're', 've', 'y',
	'ain', 'aren', "aren't", 'couldn', "couldn't", 'didn', "didn't", 'doesn', "doesn't", 'hadn', "hadn't", 'hasn', "hasn't", 'haven', "haven't",
	'isn', "isn't", 'ma', 'mightn', "mightn't", 'mustn', "mustn't", 'needn', "needn't", 'shan', "shan't", 'shouldn', "shouldn't", 'wasn', "wasn't",
	'weren', "weren't", 'won', "won't", 'wouldn', "wouldn't"
]

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
	'It is not possible to send messages in it until it enters rotation again and is available under the `✅ Help: Ask Here` category.\n\n'
	'If your question didn\'t get answered, you can claim a new channel.'
)

ASK_MESSAGE = (
	"If you're looking for scripting help you should ask in an open help channel.\n\n"
	'The currently available help channels are {1}.'
)

EDITED_ASK_MESSAGE = (
	"If you're looking for scripting help you should ask in an open help channel.\n\n"
	'See <#{}> for more information.'
)

def standardize(s: str):
	# make lowercase
	s = s.lower()

	# remove urls
	s = re.sub(r'^https?:\/\/.*[\r\n]*', '', s, flags=re.MULTILINE)

	# remove diacritics
	s = unidecode.unidecode(s)

	# remove numbers
	s = re.sub(f'[{string.digits}]', ' ', s)

	# remove punctuation
	s = re.sub(f'[{re.escape(string.punctuation)}]', ' ', s)

	# remove stopwords (and force multiple whitespaces to one)
	split = s.split()
	s = ' '.join(m for m in split if m not in STOPWORDS_EN)

	return s, len(split)


class AutoHotkeyHelpSystem(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.ask_messages = list()
		self.claimed_channel = self._load_claims()
		self.claimed_at = dict()

		self.channel_claim_lock = Lock()

		self.channel_reclaimer.start()
		self.claimed_messages = dict()

		log.debug('Loading model')
		self.model = keras.models.load_model('model')
		log.debug('Finished loading model')


	def cog_unload(self):
		self.channel_reclaimer.cancel()

	def classify(self, text):
		return self.model(np.array([standardize(text)[0]])).numpy()[0][0]

	@property
	def open_category(self):
		return self.bot.get_channel(OPEN_CATEGORY_ID)

	@property
	def active_category(self):
		return self.bot.get_channel(ACTIVE_CATEGORY_ID)

	@property
	def closed_category(self):
		return self.bot.get_channel(CLOSED_CATEGORY_ID)

	@property
	def active_info_channel(self):
		return self.bot.get_channel(ACTIVE_INFO_CHAN_ID)

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

		try:
			active_category = await self.bot.fetch_channel(ACTIVE_CATEGORY_ID)
		except discord.HTTPException:
			return

		for channel in active_category.text_channels:
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

			if last_message_at is None and claimed_at is None:
				continue

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

	async def open_channel(self, channel: discord.TextChannel):
		'''Move a channel from dormant to open.'''

		try:
			current_last = self.open_category.text_channels[-1]
			to_pos = current_last.position + 1
		except IndexError:
			to_pos = max(c.position for c in channel.guild.channels) + 1

		await channel._move(
			position=to_pos,
			parent_id=self.open_category.id,
			lock_permissions=True,
			reason=None
		)

		await self.post_message(channel, OPEN_MESSAGE, color=discord.Color.green())

	def should_open(self):
		return len(self.open_category.text_channels) < OPEN_CHANNEL_COUNT

	async def close_channel(self, channel: discord.TextChannel):
		'''Release a claimed channel from a member, making it closed.'''

		log.info(f'Closing #{channel}')

		owner_id = None

		for channel_owner_id, channel_id in self.claimed_channel.items():
			if channel_id == channel.id:
				owner_id = channel_owner_id
				break

		self.claimed_channel.pop(owner_id, None)
		self.claimed_messages.pop(channel.id, None)

		self._store_claims()

		log.info('Reclaiming %s from user id %s', po(channel), owner_id or 'UNKNOWN (not found in claims cache)')

		if self.should_open():
			log.info('Moving channel to open category since it needs channels')
			await self.open_channel(channel)
		else:
			log.info('Moving channel to closed category')

			try:
				current_first = self.closed_category.text_channels[0]
				to_pos = max(current_first.position - 1, 0)
			except IndexError:
				to_pos = max(c.position for c in channel.guild.channels) + 1

			opt = dict(
				position=to_pos,
				category=self.closed_category,
				sync_permissions=True,
				topic=f'<#{GET_HELP_CHAN_ID}>'
			)

			if self.has_postfix(channel):
				opt['name'] = self._stripped_name(channel)

			# send this before moving channel in case of rate limit shi
			try:
				await channel.send(embed=discord.Embed(description=CLOSED_MESSAGE, color=discord.Color.red()))
			except discord.HTTPException:
				pass

			await channel.edit(**opt)

	async def on_open_message(self, message):
		# so this needs a lock since people can spam messages in open channels
		# and cause a whole bigass ripple of claims happening for
		# the same channel, which calls .edit() on it a billion times
		# and also opens up a billion other channels

		# runie if you see this in the future don't remove the lock
		# just make more help channels

		async with self.channel_claim_lock:
			message: discord.Message = message
			author: discord.Member = message.author
			channel: discord.TextChannel = message.channel

			log.info(f'New message in open category: {message.author} - #{message.channel}')

			if self.is_claimed(channel.id):
				log.info('Channel is already claimed (in the claimed category?)')
				return

			# check whether author already has a claimed channel
			claimed_id = self.claimed_channel.get(author.id, None)
			if claimed_id is not None:
				log.info(f'User has already claimed #{message.guild.get_channel(claimed_id)}')
				await self.post_error(message, f'You have already claimed <#{claimed_id}>, please ask your question there.')
				return

			now = datetime.utcnow()

			# check whether author has claimed another channel within the last MINIMUM_CLAIM_INTERVAL time
			last_claim_at = self.claimed_at.get(author.id, None)
			if last_claim_at is not None and last_claim_at > now - MINIMUM_CLAIM_INTERVAL:  # and False:
				log.info(f'User previously claimed a channel {pretty_timedelta(now - last_claim_at)} ago')
				await self.post_error(message, f'Please wait at least {pretty_timedelta(MINIMUM_CLAIM_INTERVAL)} between each help channel claim.')
				return

			log.info('%s claiming %s', po(author), po(channel))

			# move channel
			try:
				opt = dict(
					position=self.active_info_channel.position + 1,
					category=self.active_category,
					sync_permissions=True,
					topic=message.jump_url
				)

				if not self.has_postfix(channel):
					opt['name'] = channel.name + '-' + NEW_EMOJI

				# set some metadata
				self.claimed_channel[author.id] = channel.id
				self.claimed_at[author.id] = now

				msgs = [message]
				self.claimed_messages[channel.id] = msgs

				await channel.edit(**opt)

				await self.maybe_yell(msgs)

			except discord.HTTPException as exc:
				log.warning('Failed moving %s to claimed category: %s', po(channel), str(exc))
				self.claimed_channel.pop(author.id, None)
				self.claimed_at.pop(author.id, None)
				self.claimed_messages.pop(channel.id, None)
				return

			self._store_claims()

		# check whether we need to move any open channels
		# this does not need to be in the lock since it's independent
		# all the other logic

		try:
			channel = self.closed_category.text_channels[-1]
		except IndexError:
			log.warning('No more openable channels in closed pool!')
		else:
			log.info(f'Opening new channel after claim: {channel}')
			await self.open_channel(channel)


		# update recent ask messages
		for msg in self.ask_messages:
			await msg.edit(content=EDITED_ASK_MESSAGE.format(GET_HELP_CHAN_ID))
		
		#clear the list since all of them have been resolved now.
		self.ask_messages = list()

	def _make_yell_embed(self, score):
		s = (
			'Your scripting question looks like it might be about a game, which is not allowed here. '
			f'Please make sure you are familiar with the <#{RULES_CHAN_ID}>, specifically rule 5.\n\n'
			'If your question does not break the rules, you can safely ignore this message. '
			'If you continue and your question is later found to break the rules, you might risk a ban.'
		)

		e = discord.Embed(
			title='Hi there!',
			description=s,
			color=discord.Color.orange()
		)

		e.set_footer(text='This message was sent by an automated system.')

		return e

	async def maybe_yell(self, msgs):
		channel = msgs[0].channel
		author = msgs[0].author
		content = ' '.join(m.content for m in msgs)

		pivot = 0.75
		c = self.classify(content)

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

			self.claimed_messages.pop(channel.id, None)

	async def on_active_message(self, message):
		if message.content.startswith('.close'):
			return

		channel = message.channel

		author_channel_id = self.claimed_channel.get(message.author.id, None)

		if author_channel_id is not None and author_channel_id == message.channel.id:
			msgs = self.claimed_messages.get(author_channel_id, None)

			# nothing there, skip for now
			if msgs is None:
				return

			msgs.append(message)

			await self.maybe_yell(msgs)
		else:
			# clear claimed_messages if someone else is talking now
			self.claimed_messages.pop(channel.id, None)

			# remove postfix if it's there
			if self.has_postfix(channel):
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
			await last_message.edit(content=None, embed=e)
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

	@commands.command(hidden=True)
	async def ask(self, ctx):
		'''Responds with the currently open for claiming channels.'''

		async with self.channel_claim_lock:
			open_category = self.open_category
			if open_category is None:
				raise commands.CommandError('Open category not found.')

			channels = [channel for channel in open_category.text_channels if channel.id != GET_HELP_CHAN_ID]
			if not channels:
				raise commands.CommandError('No help channels are currently open for claiming. Please wait for a channel to become available.')

			mentions = [c.mention for c in channels]
			mention_count = len(mentions)

			if mention_count < 3:
				ment = ' and '.join(mentions)
			else:
				mentions[-1] = 'and ' + mentions[-1]
				ment = ', '.join(mentions)

			text = ASK_MESSAGE.format(open_category, ment)

			self.ask_messages.append(await ctx.send(text))


def setup(bot):
	bot.add_cog(AutoHotkeyHelpSystem(bot))
