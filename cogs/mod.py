import argparse
import asyncio
import logging
import shlex
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from json import dumps, loads

import discord
from asyncpg.exceptions import UniqueViolationError
from discord.ext import commands

from cogs.ahk.ids import RULES_MSG_ID
from cogs.mixins import AceMixin
from utils.configtable import ConfigTable, ConfigTableRecord
from utils.context import AceContext, can_prompt, is_mod
from utils.converters import MaxLengthConverter, RangeConverter
from utils.databasetimer import DatabaseTimer
from utils.fakemember import FakeMember
from utils.string import po
from utils.time import TimeDeltaConverter, TimeMultConverter, pretty_timedelta

log = logging.getLogger(__name__)

MAX_DELTA = timedelta(days=365 * 10)
OK_EMOJI = '\U00002705'

SPAM_LOCK = asyncio.Lock()
MENTION_LOCK = asyncio.Lock()

MOD_PERMS = (
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

DEFAULT_REASON = 'No reason provided.'

PURGE_LIMIT = 512


class NoExitArgumentParser(argparse.ArgumentParser):
	def exit(self, code, error):
		raise ValueError(error)


class SecurityAction(IntEnum):
	MUTE = 1
	KICK = 2
	BAN = 3


class Severity(Enum):
	LOW = 1
	MEDIUM = 2
	HIGH = 3
	RESOLVED = 4


class SeverityColors(Enum):
	LOW = discord.Embed().color
	MEDIUM = 0xFF8C00
	HIGH = 0xFF2000
	RESOLVED = 0x32CD32


class SecurityConfigRecord(ConfigTableRecord):
	spam_cooldown = None
	mention_cooldown = None

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.create_spam_cooldown()
		self.create_mention_cooldown()

	@property
	def guild(self):
		return self._config.bot.get_guild(self.guild_id)

	@property
	def mute_role(self):
		if self.mute_role_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)

		if guild is None:
			return None

		return guild.get_role(self.mute_role_id)

	@property
	def log_channel(self):
		if self.log_channel_id is None:
			return None

		guild = self._config.bot.get_guild(self.guild_id)
		if guild is None:
			return None

		return guild.get_channel(self.log_channel_id)

	def create_spam_cooldown(self):
		self.spam_cooldown = commands.CooldownMapping.from_cooldown(
			self.spam_count, self.spam_per, commands.BucketType.user
		)

	def create_mention_cooldown(self):
		self.mention_cooldown = commands.CooldownMapping.from_cooldown(
			self.mention_count, self.mention_per, commands.BucketType.user
		)


class EventTimer(DatabaseTimer):
	async def get_record(self):
		return await self.bot.db.fetchrow(
			'SELECT * FROM mod_timer WHERE duration IS NOT NULL AND created_at + duration < $1 '
			'ORDER BY created_at + duration LIMIT 1',
			datetime.utcnow() + self.MAX_SLEEP
		)

	async def cleanup_record(self, record):
		await self.bot.db.execute('DELETE FROM mod_timer WHERE id=$1', record.get('id'))

	def when(self, record):
		return record.get('created_at') + record.get('duration')


# ripped from RoboDanny
class BannedMember(commands.Converter):
	async def convert(self, ctx, argument):
		ban_list = await ctx.guild.bans()
		try:
			member_id = int(argument, base=10)
			entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
		except ValueError:
			entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)

		if entity is None:
			raise commands.BadArgument('Not a valid previously banned member.')

		return entity


class ActionConverter(commands.Converter):
	valid_actions = ', '.join('`{0}`'.format(act.name) for act in SecurityAction)

	async def convert(self, ctx, action):
		try:
			value = SecurityAction[action.upper()]
		except KeyError:
			raise commands.BadArgument(
				'\'{0}\' is not a valid action. Valid actions are {1}'.format(
					action, self.valid_actions
				)
			)

		return value


reason_converter = MaxLengthConverter(1024)
count_converter = RangeConverter(8, 24)
interval_converter = RangeConverter(8, 24)


class Moderation(AceMixin, commands.Cog):
	'''Moderation commands to make your life simpler.'''

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(bot, 'mod_config', 'guild_id', record_class=SecurityConfigRecord)
		self.event_timer = EventTimer(bot, 'event_complete')

	@commands.Cog.listener()
	async def on_log(self, member_or_message, action=None, severity=Severity.LOW, guild=None, **fields):
		if isinstance(member_or_message, discord.Message):
			message = member_or_message
			member = message.author
			guild = message.guild
		elif isinstance(member_or_message, (discord.Member, FakeMember)):
			message = None
			member = member_or_message
			guild = member.guild
		elif isinstance(member_or_message, discord.User):
			if guild is None:
				return
			message = None
			member = member_or_message
			guild = guild
		else:
			return

		conf = await self.config.get_entry(guild.id)

		log_channel = conf.log_channel
		if log_channel is None:
			return

		desc = 'NAME: ' + str(member)
		if getattr(member, 'nick', None) is not None:
			desc += '\nAKA: ' + member.nick
		desc += '\nMENTION: ' + member.mention
		desc += '\nID: ' + str(member.id)

		color = SeverityColors[severity.name].value

		e = discord.Embed(
			title=action or 'INFO',
			description=desc,
			color=color,
			timestamp=datetime.utcnow()
		)

		for name, value in fields.items():
			e.add_field(name=name.title(), value=value, inline=False)

		if hasattr(member, 'avatar_url'):
			e.set_thumbnail(url=member.avatar_url)

		e.set_footer(text=severity.name)

		if message is not None:
			e.add_field(name='Context', value='[Click here]({})'.format(message.jump_url), inline=False)

		await log_channel.send(embed=e)

	def _craft_user_data(self, member: discord.Member):
		data = dict(
			name=member.name,
			nick=member.nick,
			discriminator=member.discriminator,
			avatar_url=str(member.avatar_url),
		)

		return dumps(data)

	@commands.command()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True)
	async def ban(self, ctx, member: discord.Member, *, reason: reason_converter = None):
		'''Ban a member. Requires Ban Members perms.'''

		try:
			await member.ban(reason=reason, delete_message_days=0)
		except discord.HTTPException:
			raise commands.CommandError('Failed banning member.')

		await ctx.send('{0} banned.'.format(str(member)))

	@commands.command()
	@can_prompt()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True)
	async def unban(self, ctx, member: BannedMember, *, reason: reason_converter = None):
		'''Unban a member. Either provide an ID or the users name and discriminator like `runie#0001`.'''

		if member.reason is None:
			prompt = 'No reason provided with the previous ban.'
		else:
			prompt = 'Ban reason:\n{0}'.format(member.reason)

		res = await ctx.prompt(title='Unban {0}?'.format(member.user), prompt=prompt)

		if not res:
			return

		try:
			await ctx.guild.unban(member.user, reason=reason)
		except discord.HTTPException:
			raise commands.CommandError('Failed unbanning member.')

		await ctx.send('{0} unbanned.'.format(str(member.user)))

	@commands.command()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def mute(self, ctx, member: discord.Member, *, reason: reason_converter = None):
		'''Mute a member. Requires Manage Roles perms.'''

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t mute this member.')

		conf = await self.config.get_entry(ctx.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			raise commands.CommandError('Mute role not set or not found.')

		if mute_role in member.roles:
			raise commands.CommandError('Member already muted.')

		try:
			await member.add_roles(mute_role, reason=reason)
		except discord.HTTPException:
			raise commands.CommandError('Mute failed.')

		try:
			await ctx.send('{0} muted.'.format(str(member)))
		except discord.HTTPException:
			pass

		self.bot.dispatch(
			'log', member, action='MUTE', severity=Severity.LOW,
			responsible=po(ctx.author), reason=reason
		)

	@commands.command()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def unmute(self, ctx, *, member: discord.Member):
		'''Unmute a member. Requires Manage Roles perms.'''

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t unmute this member.')

		conf = await self.config.get_entry(ctx.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			raise commands.CommandError('Mute role not set or not found.')

		if mute_role not in member.roles:
			raise commands.CommandError('Member not previously muted.')

		pretty_author = po(ctx.author)

		try:
			await member.remove_roles(mute_role, reason='Unmuted by {0}'.format(pretty_author))
		except discord.HTTPException:
			raise commands.CommandError('Failed removing mute role.')

		try:
			await ctx.send('{0} unmuted.'.format(str(member)))
		except discord.HTTPException:
			pass

		self.bot.dispatch(
			'log', member, action='UNMUTE', severity=Severity.RESOLVED,
			responsible=pretty_author
		)

	@commands.command()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True, embed_links=True)
	async def tempmute(self, ctx, member: discord.Member, amount: TimeMultConverter, unit: TimeDeltaConverter, *, reason: reason_converter = None):
		'''
		Temporarily mute a member. Requires Manage Role perms. Example: `tempmute @member 1 day Reason goes here.`
		'''

		now = datetime.utcnow()
		duration = amount * unit
		until = now + duration

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t mute this member.')

		if duration > MAX_DELTA:
			raise commands.CommandError('Can\'t tempmute for longer than {0}. Use `mute` instead.'.format(
				pretty_timedelta(MAX_DELTA))
			)

		conf = await self.config.get_entry(ctx.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			raise commands.CommandError('Mute role not set or not found.')

		async with self.db.acquire() as con:
			async with con.transaction():
				try:
					await con.execute(
						'INSERT INTO mod_timer (guild_id, user_id, mod_id, event, created_at, duration, reason, userdata) '
						'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
						ctx.guild.id, member.id, ctx.author.id, 'MUTE', now, duration, reason, self._craft_user_data(member)
					)
				except UniqueViolationError:
					raise commands.CommandError('Member is already muted.')

				try:
					await member.add_roles(mute_role)
				except discord.HTTPException:
					raise commands.CommandError('Failed adding mute role.')

		self.event_timer.maybe_restart(until)

		pretty_duration = pretty_timedelta(duration)

		try:
			await ctx.send('{0} tempmuted for {1}.'.format(str(member), pretty_duration))
		except discord.HTTPException:
			pass

		self.bot.dispatch(
			'log', member, action='TEMPMUTE', severity=Severity.LOW,
			responsible=po(ctx.author), duration=pretty_duration, reason=reason
		)

	@commands.command()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True, embed_links=True)
	async def tempban(self, ctx, member: discord.Member, amount: TimeMultConverter, unit: TimeDeltaConverter, *, reason: reason_converter = None):
		'''Temporarily ban a member. Requires Ban Members perms. Same formatting as `tempmute` explained above.'''

		now = datetime.utcnow()
		duration = amount * unit
		until = now + duration

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t tempban this member.')

		if duration > MAX_DELTA:
			raise commands.CommandError('Can\'t tempban for longer than {0}. Please `ban` instead.'.format(pretty_timedelta(MAX_DELTA)))

		pretty_duration = pretty_timedelta(duration)

		ban_msg = 'You have received a ban lasting {0} from {1}.\n\nReason:\n```\n{2}\n```'.format(
			pretty_duration, ctx.guild.name, reason
		)

		try:
			await member.send(ban_msg)
		except discord.HTTPException:
			pass

		async with self.db.acquire() as con:
			async with con.transaction():
				try:
					await self.db.execute(
						'INSERT INTO mod_timer (guild_id, user_id, mod_id, event, created_at, duration, reason, userdata) '
						'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
						ctx.guild.id, member.id, ctx.author.id, 'BAN', now, duration, reason, self._craft_user_data(member)
					)
				except UniqueViolationError:
					raise commands.CommandError('Member is already banned.')

				try:
					await ctx.guild.ban(member, delete_message_days=0, reason=reason)
				except discord.HTTPException:
					raise commands.CommandError('Failed banning member.')

		self.event_timer.maybe_restart(until)

		try:
			await ctx.send('{0} tempbanned for {1}.'.format(str(member), pretty_duration))
		except discord.HTTPException:
			pass

		self.bot.dispatch(
			'log', member, action='TEMPBAN', severity=Severity.HIGH,
			responsible=po(ctx.author), duration=pretty_duration, reason=reason
		)

	@commands.Cog.listener()
	async def on_event_complete(self, record):
		# relatively crucial that the bot is ready before we launch any events like tempban completions
		await self.bot.ready.wait()
		await self.bot.wait_until_ready()

		event = record.get('event')

		if event == 'MUTE':
			await self.mute_complete(record)
		elif event == 'BAN':
			await self.ban_complete(record)

	async def mute_complete(self, record):
		conf = await self.config.get_entry(record.get('guild_id'))
		mute_role = conf.mute_role

		if mute_role is None:
			return

		guild_id = record.get('guild_id')
		user_id = record.get('user_id')
		mod_id = record.get('mod_id')
		duration = record.get('duration')
		reason = record.get('reason')

		guild = self.bot.get_guild(guild_id)
		if guild is None:
			return

		member = guild.get_member(user_id)
		if member is None:
			return

		mod = guild.get_member(mod_id)
		pretty_mod = '(ID: {0})'.format(str(mod_id)) if mod is None else po(mod)

		try:
			await member.remove_roles(mute_role, reason='Completed tempmute issued by {0}'.format(pretty_mod))
		except discord.HTTPException:
			return

		self.bot.dispatch(
			'log', member, action='TEMPMUTE COMPLETED', severity=Severity.RESOLVED,
			responsible=pretty_mod, duration=pretty_timedelta(duration), reason=reason
		)

	async def ban_complete(self, record):
		guild_id = record.get('guild_id')
		user_id = record.get('user_id')
		mod_id = record.get('mod_id')
		duration = record.get('duration')
		userdata = loads(record.get('userdata'))
		reason = record.get('reason')

		guild = self.bot.get_guild(guild_id)
		if guild is None:
			return

		mod = guild.get_member(mod_id)
		pretty_mod = '(ID: {0})'.format(str(mod_id)) if mod is None else po(mod)

		try:
			await guild.unban(discord.Object(id=user_id), reason='Completed tempban issued by {0}'.format(pretty_mod))
		except discord.HTTPException:
			return  # rip :)

		member = FakeMember(guild, user_id, **userdata)

		self.bot.dispatch(
			'log', member, action='TEMPBAN COMPLETED', severity=Severity.RESOLVED,
			responsible=pretty_mod, duration=pretty_timedelta(duration), reason=reason
		)

	@commands.Cog.listener()
	async def on_member_unban(self, guild, user):
		# remove tempbans if user is manually unbanned
		_id = await self.db.fetchval(
			'DELETE FROM mod_timer WHERE guild_id=$1 AND user_id=$2 AND event=$3 RETURNING id',
			guild.id, user.id, 'BAN'
		)

		# also restart timer if the next in line *was* that tempban
		if _id is not None:
			self.event_timer.restart_if(lambda r: r.get('id') == _id)

			self.bot.dispatch(
				'log', user, action='TEMPBAN CANCELLED', severity=Severity.RESOLVED, guild=guild,
				reason='Tempbanned member manually unbanned.'
			)

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		if before.bot:
			return

		if before.roles == after.roles:
			return

		conf = await self.config.get_entry(before.guild.id)
		mute_role_id = conf.mute_role_id

		if mute_role_id is None:
			return

		# neat
		before_has = before._roles.has(mute_role_id)
		after_has = after._roles.has(mute_role_id)

		if before_has == after_has:
			return

		if before_has:
			# mute role removed
			_id = await self.db.fetchval(
				'DELETE FROM mod_timer WHERE guild_id=$1 AND user_id=$2 AND event=$3 RETURNING id',
				after.guild.id, after.id, 'MUTE'
			)

			self.event_timer.restart_if(lambda r: r.get('id') == _id)

		elif after_has:  # not strictly necessary but more explicit
			# mute role added
			try:
				await self.db.execute(
					'INSERT INTO mod_timer (guild_id, user_id, event, created_at, userdata) '
					'VALUES ($1, $2, $3, $4, $5)',
					after.guild.id, after.id, 'MUTE', datetime.utcnow(), self._craft_user_data(after)
				)
			except UniqueViolationError:
				return

	@commands.Cog.listener()
	async def on_member_join(self, member):
		if member.bot:
			return

		conf = await self.config.get_entry(member.guild.id)
		mute_role_id = conf.mute_role_id

		if mute_role_id is None:
			return

		# check if member was previously muted
		_id = await self.db.fetchval(
			'SELECT id FROM mod_timer WHERE guild_id=$1 AND user_id=$2 AND event=$3',
			member.guild.id, member.id, 'MUTE'
		)

		if _id is None:
			return

		mute_role = conf.mute_role
		if mute_role is None:
			return

		reason = 'Re-muting newly joined member who was previously muted'

		await member.add_roles(mute_role, reason=reason)
		self.bot.dispatch('log', member, action='MUTE', severity=Severity.LOW, reason=reason)

	@commands.command()
	@commands.has_permissions(manage_messages=True)
	@commands.bot_has_permissions(manage_messages=True)
	async def clear(self, ctx, message_count: int, user: discord.Member = None):
		'''Simple purge command. Clear messages, either from user or indiscriminately.'''

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

		try:
			await ctx.message.delete()
		except discord.HTTPException:
			pass

		try:
			deleted = await ctx.channel.purge(limit=message_count, check=all_check if user is None else user_check)
		except discord.HTTPException:
			raise commands.CommandError('Failed deleting messages. Does the bot have the necessary permissions?')

		count = len(deleted)

		log.info('%s cleared %s messages in %s', po(ctx.author), count, po(ctx.guild))

		await ctx.send(f'Deleted {count} message{"s" if count > 1 else ""}.', delete_after=5)

	@commands.command()
	@commands.has_permissions(manage_messages=True)
	@commands.bot_has_permissions(manage_messages=True)
	async def purge(self, ctx, *, args: str = None):
		'''Advanced purge command. Do `help purge` for usage examples and argument list.

		Arguments are parsed as command line arguments.

		Examples:
		Delete all messages within the last 200 containing the word "spam": `purge --check 200 --contains "spam"`
		Delete all messages within the last 100 from two members: `purge --user @runie @dave`
		Delete maximum 6 messages within the last 400 starting with "ham": `purge --check 400 --max 6 --starts "ham"`

		List of arguments:
		```
		--check <int>
		Total amount of messages the bot will check for deletion.

		--max <int>
		Total amount of messages the bot will delete.

		--bot
		Only delete messages from bots.

		--user member [...]
		Only delete messages from these members.

		--after message_id
		Start deleting after this message id.

		--before message_id
		Delete, at most, up until this message id.

		--contains
		Delete messages containing this string(s).

		--starts <string>
		Delete messages starting with this string(s).

		--ends <string>
		Delete messages ending with this string(s).```'''

		parser = NoExitArgumentParser(prog='purge', add_help=False, allow_abbrev=False)

		parser.add_argument('-c', '--check', type=int, metavar='message_count', help='Total amount of messages checked for deletion.')
		parser.add_argument('-m', '--max', type=int, metavar='message_count', help='Total amount of messages the bot will delete.')
		parser.add_argument('--bot', action='store_true', help='Only delete messages from bots.')
		parser.add_argument('-u', '--user', nargs='+', metavar='user', help='Only delete messages from this member(s).')
		parser.add_argument('-a', '--after', type=int, metavar='id', help='Start deleting after this message id.')
		parser.add_argument('-b', '--before', type=int, metavar='id', help='Delete, at most, up until this message id.')
		parser.add_argument('--contains', nargs='+', metavar='text', help='Delete messages containing this string(s).')
		parser.add_argument('--starts', nargs='+', metavar='text', help='Delete messages starting with this string(s).')
		parser.add_argument('--ends', nargs='+', metavar='text', help='Delete messages ending with this string(s).')

		if args is None:
			await ctx.send('```\n{0}\n```'.format(parser.format_help()))
			return

		try:
			args = parser.parse_args(shlex.split(args))
		except Exception as e:
			raise commands.CommandError(str(e).partition('error: ')[2])

		preds = [lambda m: m.id != ctx.message.id, lambda m: m.id != RULES_MSG_ID]

		if args.user:
			converter = commands.MemberConverter()
			members = []

			for id in args.user:
				try:
					member = await converter.convert(ctx, id)
					members.append(member)
				except commands.CommandError:
					raise commands.CommandError('Unknown user: "{0}"'.format(id))

			preds.append(lambda m: m.author in members)

		if args.contains:
			preds.append(lambda m: any((s in m.content) for s in args.contains))

		if args.bot:
			preds.append(lambda m: m.author.bot)

		if args.starts:
			preds.append(lambda m: any(m.content.startswith(s) for s in args.starts))

		if args.ends:
			preds.append(lambda m: any(m.content.endswith(s) for s in args.ends))

		count = args.max
		deleted = 0

		def predicate(message):
			nonlocal deleted

			if count is not None and deleted >= count:
				return False

			if all(pred(message) for pred in preds):
				deleted += 1
				return True

		# limit is 100 be default
		limit = 100
		after = None
		before = None

		# set to 512 if after flag is set
		if args.after:
			after = discord.Object(id=args.after)
			limit = PURGE_LIMIT

		if args.before:
			before = discord.Object(id=args.before)

		# if we actually want to manually specify it doe
		if args.check is not None:
			limit = max(0, min(PURGE_LIMIT, args.check))

		try:
			deleted_messages = await ctx.channel.purge(limit=limit, check=predicate, before=before, after=after)
		except discord.HTTPException:
			raise commands.CommandError('Error occurred when deleting messages.')

		deleted_count = len(deleted_messages)

		log.info('%s purged %s messages in %s', po(ctx.author), deleted_count, po(ctx.guild))

		await ctx.send('{0} messages deleted.'.format(deleted_count), delete_after=10)

	@commands.command()
	@commands.has_permissions(administrator=True)
	async def muterole(self, ctx, *, role: discord.Role = None):
		'''Set the mute role. Only modifiable by server administrators. Leave argument empty to clear.'''

		conf = await self.config.get_entry(ctx.guild.id)

		if role is None:
			await conf.update(mute_role_id=None)
			await ctx.send('Mute role cleared.')
		else:
			await conf.update(mute_role_id=role.id)
			await ctx.send('Mute role has been set to {0}'.format(po(role)))

	@commands.command()
	@is_mod()
	async def logchannel(self, ctx, *, channel: discord.TextChannel = None):
		'''Set a channel for the bot to log moderation-related messages.'''

		conf = await self.config.get_entry(ctx.guild.id)

		if channel is None:
			await conf.update(log_channel_id=None)
			await ctx.send('Log channel cleared.')
		else:
			await conf.update(log_channel_id=channel.id)
			await ctx.send('Log channel has been set to {0}'.format(po(channel)))

	@commands.command(hidden=True)
	@is_mod()
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
				if slot in MOD_PERMS:
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

	async def do_action(self, message, action, reason):
		'''Called when an event happens.'''

		member = message.author

		conf = await self.config.get_entry(member.guild.id)
		ctx = await self.bot.get_context(message, cls=AceContext)

		# ignore if member is mod
		if await ctx.is_mod():
			self.bot.dispatch(
				'log', message,
				action='IGNORED {0} (MEMBER IS MOD)'.format(action.name),
				severity=Severity.LOW, reason=reason,
			)

			return

		# otherwise, check against security actions and perform punishment
		try:
			if action is SecurityAction.MUTE:
				mute_role = conf.mute_role

				if mute_role is None:
					raise ValueError('No mute role set.')

				await member.add_roles(mute_role, reason=reason)

			elif action is SecurityAction.KICK:
				await member.kick(reason=reason)

			elif action is SecurityAction.BAN:
				await member.ban(delete_message_days=0, reason=reason)

		except Exception as exc:
			# log error if something happened
			self.bot.dispatch(
				'log', message,
				action='{0} FAILED'.format(action.name),
				severity=Severity.HIGH,
				reason=reason, error=str(exc)
			)
			return

		# log successful security event
		self.bot.dispatch(
			'log', message,
			action=action.name, severity=Severity(action.value),
			reason=reason
		)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None:
			return

		if message.author.bot:
			return

		mc = await self.config.get_entry(message.guild.id, construct=False)

		if mc is None:
			return

		if mc.spam_action is not None:
			# with a lock, figure out if user is spamming
			async with SPAM_LOCK:
				res = mc.spam_cooldown.update_rate_limit(message)
				if res is not None:
					mc.spam_cooldown._cache[mc.spam_cooldown._bucket_key(message)].reset()

			# if so, perform the spam action
			if res is not None:
				await self.do_action(
					message, SecurityAction[mc.spam_action], reason='Member is spamming'
				)

		if mc.mention_action is not None and message.mentions:

			# same here. however run once for each mention
			async with MENTION_LOCK:
				for mention in message.mentions:
					res = mc.mention_cooldown.update_rate_limit(message)
					if res is not None:
						mc.mention_cooldown._cache[mc.mention_cooldown._bucket_key(message)].reset()
						break

			if res is not None:
				await self.do_action(
					message, SecurityAction[mc.mention_action], reason='Member is mention spamming'
				)

	def _craft_string(self, ctx, type, conf, now=False):
		'''This particular thing is a fucking mess but I'm over it'''

		type = type.lower()

		action = getattr(conf, type + '_action')
		count = getattr(conf, type + '_count')
		per = getattr(conf, type + '_per')

		data = (
			'{0} action is{3}performed on members sending `{1}` '
			'or more {4} within `{2}` seconds.'
		).format(
			'A `{0}`'.format(action) if action else 'No', count, per,
			' now ' if now else ' ', 'mentions' if type == 'mention' else 'messages'
		)

		perms = ctx.perms

		if action == 'MUTE' and conf.mute_role_id is None:
			data += '\n\nNOTE: You do not have a mute role set up. Use `muterole <role>`!'
		elif action == 'BAN' and not perms.ban_members:
			data += '\n\nNOTE: I do not have Ban Members permissions!'
		elif action == 'KICK' and not perms.kick_members:
			data += '\n\nNOTE: I do not have Kick Members permissions!'
		elif action is None:
			data += '\n\nNOTE: Anti-{0} is disabled, enable by doing `{0} action <action>`'.format(type)
		else:
			data += '\n\nNo issues found with current configuration. Anti-{0} is live!'.format(type)

		return data

	@commands.group(invoke_without_command=True)
	@is_mod()
	async def spam(self, ctx):
		'''View current anti-spam settings.'''

		conf = await self.config.get_entry(ctx.guild.id)
		await ctx.send(self._craft_string(ctx, 'spam', conf))

	@spam.command(name='action')
	@is_mod()
	async def antispam_action(self, ctx, *, action: ActionConverter = None):
		'''Set action taken towards spamming members. Valid actions are `MUTE`, `KICK`, and `BAN`. Leave argument blank to disable anti-spam.'''

		conf = await self.config.get_entry(ctx.guild.id)
		await conf.update(spam_action=None if action is None else action.name)

		if action is None:
			data = 'Anti-spam disabled.'
		else:
			data = self._craft_string(ctx, 'spam', conf, now=True)

		await ctx.send(data)

	@spam.command(name='rate')
	@is_mod()
	async def antispam_rate(self, ctx, count: count_converter, interval: interval_converter):
		'''A member is spamming if they send `count` or more messages in `interval` seconds.'''

		conf = await self.config.get_entry(ctx.guild.id)
		await conf.update(spam_count=count, spam_per=interval)

		conf.create_spam_cooldown()

		await ctx.send(self._craft_string(ctx, 'spam', conf, now=True))

	@commands.group(invoke_without_command=True)
	@is_mod()
	async def mention(self, ctx):
		'''View current anti-mentionspam settings.'''

		conf = await self.config.get_entry(ctx.guild.id)
		await ctx.send(self._craft_string(ctx, 'mention', conf))

	@mention.command(name='action')
	@is_mod()
	async def mention_action(self, ctx, *, action: ActionConverter = None):
		'''Action taken towards mention-spamming members. Valid actions are `MUTE`, `KICK`, and `BAN`. Leave argument blank to disable anti-mention.'''

		conf = await self.config.get_entry(ctx.guild.id)
		await conf.update(mention_action=None if action is None else action.name)

		if action is None:
			data = 'Anti-mention disabled.'
		else:
			data = self._craft_string(ctx, 'mention', conf, now=True)

		await ctx.send(data)

	@mention.command(name='rate')
	@is_mod()
	async def mention_rate(self, ctx, count: count_converter, interval: interval_converter):
		'''A member is mention-spamming if they send `count` or more mentions in `interval` seconds.'''

		conf = await self.config.get_entry(ctx.guild.id)
		await conf.update(mention_count=count, mention_per=interval)

		conf.create_mention_cooldown()

		await ctx.send(self._craft_string(ctx, 'mention', conf, now=True))


def setup(bot):
	bot.add_cog(Moderation(bot))
