from datetime import datetime
from typing import Union

import disnake
from disnake.ext import commands

from ace import AceBot
from cogs.mixins import AceMixin
from utils.context import AceContext
from utils.string import po


class InternalLogger(commands.Cog, AceMixin):

	@commands.Cog.listener()
	async def on_command(self, ctx: Union[AceContext, disnake.Interaction]):
		spl = ctx.message.content.split('\n')
		self.bot.log.info('%s in %s: %s', po(ctx.author), po(ctx.guild), spl[0] + (' ...' if len(spl) > 1 else ''))

	@commands.Cog.listener()
	async def on_command_completion(self, ctx: AceContext):
		await self.bot.db.execute(
			'INSERT INTO log (guild_id, channel_id, user_id, timestamp, command, type) VALUES ($1, $2, $3, $4, $5, $6)',
			ctx.guild.id, ctx.channel.id, ctx.author.id, datetime.utcnow(), ctx.command.qualified_name, 'PREFIX'
		)

	@commands.Cog.listener()
	async def on_slash_command_completion(self, inter: disnake.ApplicationCommandInteraction):
		await self.bot.db.execute(
			'INSERT INTO log (guild_id, channel_id, user_id, timestamp, command, type) VALUES ($1, $2, $3, $4, $5, $6)',
			inter.guild.id, inter.channel.id, inter.author.id, datetime.utcnow(), inter.application_command.qualified_name, 'APPLICATION'
		)


def setup(bot: AceBot):
	bot.add_cog(InternalLogger(bot))
