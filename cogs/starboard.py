import discord
from discord.ext import commands

from .base import TogglableCogMixin
from utils.database import StarGuild, StarMessage

STAR_EMOJI = '⭐'

class Starboard(TogglableCogMixin):
	'''Classic starboard.'''

	async def __local_check(self, ctx):
		return await self._is_used(ctx)

	async def on_raw_reaction_add(self, payload):
		if str(payload.emoji) != STAR_EMOJI:
			return

		if not await self.bot.uses_module(payload.guild_id, 'starboard'):
			return

		print('yas')

	async def _star(self, guild_id, starrer_id, message):
		pass

	@commands.command()
	async def star(self, ctx, message_id: int):
		'''Star a message.'''

	@commands.command()
	async def unstar(self, ctx, message_id: int):
		'''Unstar a message you previously starred.'''


def setup(bot):
	bot.add_cog(Starboard(bot))
