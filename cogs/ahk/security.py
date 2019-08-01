import discord
import asyncio
import logging

from discord.ext import commands
from datetime import datetime

from cogs.mixins import AceMixin
from cogs.ahk.ids import *
from utils.string_helpers import craft_welcome
from utils.severity import SeverityColors

log = logging.getLogger(__name__)


WELCOME_MSG = '''
Welcome to our Discord community, {user}!
You can find recent announcements in <#367301754729267202>, and give yourself roles in <#513071256283906068>!
'''

ACCEPT_EMOJI = '\N{WHITE HEAVY CHECK MARK}'


class AutoHotkeySecurity(AceMixin, commands.Cog):
	'''AHK Security.'''

	def __init__(self, bot):
		super().__init__(bot)
		self.log = bot.get_cog('Security').log

	async def on_raw_reaction_add(self, pl):
		if pl.channel_id != WELCOME_CHAN_ID or pl.message_id != RULES_MSG_ID:
			return

		guild = self.bot.get_guild(pl.guild_id)
		channel = guild.get_channel(pl.channel_id)
		member = guild.get_member(pl.user_id)
		member_role = guild.get_role(MEMBER_ROLE_ID)

		if str(pl.emoji) != ACCEPT_EMOJI:
			msg = await channel.fetch_message(pl.message_id)
			await msg.remove_reaction(pl.emoji, member)
			return

		if member_role is None:
			await self.log(f'<@&{STAFF_ROLE_ID}> Member role not found during member accept.')
			return

		if member_role in member.roles:
			return

		reason = 'User accepted the rules.'

		try:
			await member.add_roles(member_role, reason=reason)
		except Exception as exc:
			await self.log(f'<@&{STAFF_ROLE_ID}>: Failed adding member role.\n\nError:\n' + str(exc))
			return

		general_channel = guild.get_channel(GENERAL_CHAN_ID)
		if general_channel is None:
			await self.log(f'<@&{STAFF_ROLE_ID}>: Couldn\'t find the #general channel when accepting member.')
			return

		# sleep for 2 secs and send the welcome message
		await asyncio.sleep(2)
		await general_channel.send(craft_welcome(member, WELCOME_MSG))

		log.info('{} ({}) accepted into server.'.format(member.name, member.id))

		await self.log(
			action='Member accepted',
			reason=reason,
			severity=SeverityColors.LOW,
			author=member,
			channel=guild.get_channel(MISC_CHAN_ID)
		)


def setup(bot):
	bot.add_cog(AutoHotkeySecurity(bot))
