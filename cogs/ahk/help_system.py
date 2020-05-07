import discord
import os
import shutil
import subprocess
import logging

from datetime import datetime, timedelta

from discord import ChannelType
from discord.ext import commands
from discord.ext import tasks

from cogs.ahk.ids import *
from cogs.mixins import AceMixin

from utils.string import po

from cogs.ahk.ids import CLAIMED_CATEGORY_ID, POOL_CATEGORY_ID, AHK_GUILD_ID, OPEN_CATEGORY_ID

from collections import defaultdict
from utils.context import is_mod

from asyncio import Lock


FREE_AFTER = timedelta(seconds=10)

GUIDE_MESSAGE = '''
This help channel is now open, which means you can claim it by simply asking a question here. 
Once claimed, the channel will be moved into the 'CLAIMED' category, and will be claimed for 30 minutes after a message is sent, or until you manually free the channel with `.free`.
When a channel is freed, it is reused for another question later on.
'''


log = logging.getLogger(__name__)


class AutoHotkeyHelpSystem(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.claim_lock = Lock()
		self.release_lock = Lock()

		self.claimed = dict()
		self.channel_reclaimer.start()

		self.claimed_category = bot.get_channel(CLAIMED_CATEGORY_ID)
		self.pool_category = bot.get_channel(POOL_CATEGORY_ID)
		self.open_category = bot.get_channel(OPEN_CATEGORY_ID)

	@commands.Cog.listener()
	async def on_help_release(self, channel):
		async with self.release_lock:
			owner_id = None

			for channel_owner_id, channel_id in self.claimed.items():
				if channel_id == channel.id:
					owner_id = channel_owner_id

			if owner_id is not None:
				self.claimed.pop(owner_id)
		
			log.info('Reclaming %s from user id %s', po(channel), owner_id)

			await channel.edit(category=self.pool_category, topic='Open for claiming.', sync_permissions=True)

	@commands.Cog.listener()
	async def on_help_claim(self, channel, member):
		async with self.claim_lock:
			self.claimed[member.id] = channel.id

			log.info('%s claiming %s', po(member), po(channel))

			try:
				await channel.edit(category=self.claimed_category, topic=f'Channel claimed by {member.name}.', sync_permissions=True)
			except discord.HTTPException:	
				log.warning('Failed moving %s to claimed category.', po(channel))
				return

			if len(self.open_category.text_channels) >= 5:
				return

			try:
				new_channel = self.pool_category.text_channels[-1]
			except IndexError:
				log.warning('No more channels in pool.')
				return

			try:
				await new_channel.edit(category=self.open_category, topic='Type a message in this channel to claim it', sync_permissions=True)
				await new_channel.send(GUIDE_MESSAGE)
			except discord.HTTPException:
				log.warning('Failed moving pool channel %s to ', po(new_channel))

	@tasks.loop(seconds=5)
	async def channel_reclaimer(self):
		on_age = datetime.utcnow() - FREE_AFTER

		for channel in self.claimed_category.text_channels:
			last_message = channel.last_message
			if last_message is None:
				last_message = (await channel.fetch_message(channel.last_message_id))

			message_time = last_message.created_at

			if message_time < on_age:
				self.bot.dispatch('help_release', channel)


	@commands.Cog.listener()
	async def on_message(self, message):
		guild = message.guild

		if guild is None:# or guild.id != AHK_GUILD_ID:
			return

		author = message.author

		if author.bot:
			return

		channel: discord.TextChannel = message.channel
		category: discord.CategoryChannel = channel.category

		if category is None or category.id != OPEN_CATEGORY_ID:
			return

		if author.id in self.claimed:
			await channel.send(f'{author.mention} you have already claimed <#{self.claimed[author.id]}>, please ask your question in that channel.')
		else:
			self.bot.dispatch('help_claim', channel, author)

	@commands.command()
	async def close(self, ctx):
		''' Un-claims a help channel, and moves it back into the pool of available help channels. '''

		is_mod = await ctx.is_mod()
		
		if is_mod or self.claimed.get(ctx.author.id, None) == ctx.channel.id:
			if is_mod:
				log.info('%s manually closing %s', po(ctx.author), po(ctx.channel))
			
			self.bot.dispatch('help_release', ctx.channel)
		else:
			raise commands.CommandError('You can\'t do that.')
			

def setup(bot):
	bot.add_cog(AutoHotkeyHelpSystem(bot))
