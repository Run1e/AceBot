import discord
import logging

from discord.ext import commands

from cogs.mixins import AceMixin
from cogs.ahk.ids import RULES_MSG_ID
from utils.checks import is_mod_pred
from utils.pager import Pager
from utils.time import pretty_datetime

log = logging.getLogger(__name__)


class DiscordObjectPager(Pager):
	async def craft_page(self, e, page, entries):
		entry = entries[0]

		e.description = ''

		if hasattr(entry, 'mention'):
			e.description = entry.mention

		if hasattr(entry, 'avatar_url'):
			e.set_author(name=entry.name, icon_url=entry.avatar_url)
		elif hasattr(entry, 'name'):
			e.title = entry.name

		e.add_field(name='ID', value=entry.id)

		if hasattr(entry, 'created_at'):
			e.add_field(name='Created at', value=pretty_datetime(entry.created_at))

		if hasattr(entry, 'joined_at'):
			e.add_field(name='Joined at', value=pretty_datetime(entry.joined_at))

		if hasattr(entry, 'colour'):
			e.add_field(name='Color', value=entry.colour)

		if hasattr(entry, 'mentionable'):
			e.add_field(name='Mentionable', value='Yes' if entry.mentionable else 'No')

		if hasattr(entry, 'topic'):
			e.description += '\n\n' + entry.topic if len(e.description) else entry.topic

		if hasattr(entry, 'position'):
			e.add_field(name='Position', value=entry.position)

		e.set_footer(text=str(type(entry))[8:-2])


class Moderator(AceMixin, commands.Cog):
	'''Commands available to moderators.'''

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
	async def get(self, ctx, object, key=None, *, value=None):
		'''Get a discord object by specifying key and value.'''

		if value is None and key is not None:
			raise commands.CommandError('Invalid arguments.')

		obj_list = dict(
			member=ctx.guild.members,
			emoji=ctx.guild.emojis,
			channel=ctx.guild.channels,
			role=list(reversed(ctx.guild.roles[1:])),
			category=ctx.guild.categories,
			categorie=ctx.guild.categories,
		)

		if object[-1] == 's':
			object = object[:-1]

		if object not in obj_list:
			raise commands.CommandError('Unknown object type.')

		objects = obj_list[object]

		if not len(objects):
			raise commands.CommandError('No objects of this type on this server.')

		if key is not None:
			obj = discord.utils.get(objects, **{key: value})
			if obj is None:
				try:
					obj = discord.utils.get(objects, **{key: int(value)})
				except ValueError:
					pass
			objects = [obj]
			if objects[0] is None:
				raise commands.CommandError('Not found.')

		p = DiscordObjectPager(ctx, entries=objects, per_page=1)
		await p.go()

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
