import discord
import logging

from discord.ext import commands

from cogs.mixins import AceMixin
from cogs.ahk.ids import RULES_MSG_ID
from utils.checks import is_mod_pred

log = logging.getLogger(__name__)


class Moderator(AceMixin, commands.Cog):
	'''Simple moderation commands.'''

	mod_perms = (
		'administrator',
		'kick_members',
		'ban_members',
		'manage_guild',
		'manage_roles',
		'manage_channels',
		'manage_messages',
		'manage_nicknames',
		'manage_webhooks',
		'manage_emojis',
		'mention_everyone',
		'mute_members',
		'move_members',
		'view_audit_log',
		'deafen_members',
		'priority_speaker'
	)

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	@commands.command()
	@commands.bot_has_permissions(manage_messages=True)
	async def clear(self, ctx, message_count: int, user: discord.Member = None):
		'''Clear messages, either from user or indiscriminately.'''

		if message_count < 1:
			raise commands.CommandError('Please choose a positive message amount to clear.')

		if message_count > 100:
			raise commands.CommandError('Please choose a message count below 100.')

		def all_check(msg):
			if msg.id == RULES_MSG_ID:
				return False
			return True

		def user_check(msg):
			return msg.author == user and all_check(msg)

		await ctx.message.delete()
		deleted = await ctx.channel.purge(limit=message_count, check=all_check if user is None else user_check)

		count = len(deleted)

		log.info('{} ({}) deleted {} messages in #{} ({})'.format(
			ctx.author.name, ctx.author.id, count, ctx.channel.name, ctx.channel.id)
		)

		await ctx.send(f'Deleted {count} message{"s" if count > 1 else ""}.', delete_after=5)

	@commands.command()
	async def perms(self, ctx, user: discord.Member = None, channel: discord.TextChannel = None):
		'''Lists a users permissions in a channel.'''

		if user is None:
			user = ctx.author

		if channel is None:
			channel = ctx.channel

		perms = user.permissions_in(channel)

		mod_perms = []
		general_perms = []

		for slot in dir(perms):
			if slot.startswith('_'):
				continue
			if getattr(perms, slot) is True:
				if slot in self.mod_perms:
					mod_perms.append(slot)
				else:
					general_perms.append(slot)

		content = ''

		if len(mod_perms):
			content += '```' + '\n'.join(mod_perms) + '```'

		if len(general_perms):
			content += '```' + '\n'.join(general_perms) + '```'

		if not len(content):
			content = f'No permissions in channel {channel.mention}'

		await ctx.send(content)



def setup(bot):
	bot.add_cog(Moderator(bot))
