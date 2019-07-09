
import discord
from discord.ext import commands

from cogs.mixins import AceMixin, ToggleMixin

"""

antimention, allow guild mods to set:
- mention count (n) per seconds (s) (for example, max 6 mentions per minute)
- 


commands:
.muterole [role]
.muteopt
"""

class Security(AceMixin, ToggleMixin, commands.Cog):

	_mentions = {}

	def __init__(self, bot):
		super().__init__(bot)

		self.create_mention_cooldown(517692823621861407, 1, 5)

	def create_mention_cooldown(self, guild_id, count, per):
		self._mentions[guild_id] = commands.CooldownMapping.from_cooldown(count, per, commands.BucketType.member)

	def remove_mention_cooldown(self, guild_id):
		if guild_id in self._mentions:
			self._mentions.pop(guild_id)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild.id not in self._mentions:
			return

		# make sure cog is in use
		if not await self.cog_check(message):
			return

		for mention in message.mentions:
			if self._mentions[message.guild.id].update_rate_limit(message) is not None:
				await self.mention_handler(message)
			# TODO: also loop over role mentions??

	async def mention_handler(self, message):
		print(message)


def setup(bot):
	bot.add_cog(Security(bot))