import discord
from discord.ext import commands
from datetime import datetime

from cogs.base import TogglableCogMixin
from utils.time import pretty_seconds


class Moderator(TogglableCogMixin):
	'''
	Moderation commands.
	
	Only available for members with Ban Members permissions.
	'''

	# user in perms command
	mod_perms = (
		'administrator',
		'kick_members',
		'ban_members',
		'manage_guild',
		'manage_roles',
		'manage_channels',
		'manage_messages',
		'manage_webhooks',
		'manage_emojis',
		'mention_everyone',
		'mute_members',
		'move_members',
		'deafen_members',
		'priority_speaker'
	)

	async def __local_check(self, ctx):
		return await self._is_used(ctx) and ctx.author.permissions_in(ctx.channel).ban_members

	@commands.command()
	async def perms(self, ctx, user: discord.Member = None, channel: discord.TextChannel = None):
		'''Lists a users permissions in a channel.'''

		if user is None:
			user = ctx.author

		if channel is None:
			channel = ctx.channel

		perms = user.permissions_in(channel)

		if perms.administrator:
			await ctx.send('User is administrator.')
			return

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

	@commands.command()
	async def info(self, ctx, user: discord.Member = None):
		'''Display information about user or self.'''

		if user is None:
			user = ctx.author

		e = discord.Embed(description='')

		if user.bot:
			e.description = 'This account is a bot.\n'

		e.description += user.mention

		e.add_field(name='Status', value=user.status)

		if user.activity:
			e.add_field(name='Activity', value=user.activity)

		e.set_author(name=f'{user.name}#{user.discriminator}', icon_url=user.avatar_url)

		now = datetime.now()
		created = user.created_at
		joined = user.joined_at

		e.add_field(
			name='Account age',
			value=f'{pretty_seconds((now - created).total_seconds())}\nCreated {created.day}/{created.month}/{created.year}'
		)

		e.add_field(
			name='Member for',
			value=f'{pretty_seconds((now - joined).total_seconds())}\nJoined {joined.day}/{joined.month}/{joined.year}'
		)

		if len(user.roles) > 1:
			e.add_field(name='Roles', value=' '.join(role.mention for role in reversed(user.roles[1:])))

		e.set_footer(text='ID: ' + str(user.id))

		await ctx.send(embed=e)

	@commands.command()
	@commands.bot_has_permissions(manage_messages=True)
	async def clear(self, ctx, message_count: int = None, user: discord.Member = None):
		'''Clear messages, either from user or indiscriminately.'''

		if message_count is None:
			return await ctx.send('Please choose a message count.')

		if message_count > 100:
			return await ctx.send('Please choose a message count below 100.')

		if user is not None:
			check = lambda msg: msg.author == user
		else:
			check = None

		await ctx.message.delete()
		deleted = await ctx.channel.purge(limit=message_count, check=check)

		await ctx.send(f'\U0000274C Deleted {len(deleted)} messages.', delete_after=5)


def setup(bot):
	bot.add_cog(Moderator(bot))
