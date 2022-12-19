import argparse
import asyncio
import io
import logging
import shlex
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from json import dumps, loads
from typing import Union

import disnake
from asyncpg.exceptions import UniqueViolationError
from disnake.ext import commands

from cogs.mixins import AceMixin
from ids import AHK_GUILD_ID, RULES_MSG_ID, LEVEL_ROLE_IDS
from utils.configtable import ConfigTable, ConfigTableRecord
from utils.context import AceContext, can_prompt, is_mod
from utils.converters import MaxLengthConverter, MaybeMemberConverter, RangeConverter
from utils.databasetimer import DatabaseTimer
from utils.fakeuser import FakeUser
from utils.string import po
from utils.time import TimeDeltaConverter, TimeMultConverter, pretty_timedelta

log = logging.getLogger(__name__)

MAX_DELTA = timedelta(days=365 * 10)
OK_EMOJI = '\U00002705'

SPAM_LOCK = asyncio.Lock()
MENTION_LOCK = asyncio.Lock()
CONTENT_LOCK = asyncio.Lock()

MOD_PERMS = (
	'administrator',
	'ban_members',
	'kick_members',
	'moderate_members',
	'manage_guild',
	'manage_channels',
	'manage_threads',
	'manage_messages',
	'manage_emojis',
	'manage_nicknames',
	'manage_permissions',
	'manage_roles',
	'manage_webhooks',
	'manage_events',
	'mention_everyone',
	'create_private_threads',
	'view_audit_log',
	'view_guild_insights',
	'send_tts_messages',
	'move_members',
	'deafen_members',
	'mute_members',
	'priority_speaker',
	#'attach_files',  # "useful" to know but causes a lot of noise
)

DEFAULT_REASON = 'No reason provided.'

PURGE_LIMIT = 512


class NoExitArgumentParser(argparse.ArgumentParser):
	def exit(self, code, error):
		raise ValueError(error)


class SecurityAction(IntEnum):
	TIMEOUT = 1
	KICK = 2
	BAN = 3


class SecurityVerb(Enum):
	TIMEOUT = 'timed out (for 28 days)'
	KICK = 'kicked'
	BAN = 'banned'


class Severity(Enum):
	LOW = 1
	MEDIUM = 2
	HIGH = 3
	RESOLVED = 4


class SeverityColors(Enum):
	LOW = disnake.Embed().color
	MEDIUM = 0xFF8C00
	HIGH = 0xFF2000
	RESOLVED = 0x32CD32


OTHER_CHANNEL_PENALTY = 2


class CooldownByContent(commands.CooldownMapping):
	def __init__(self, original, type):
		super().__init__(original, type)

		self.bucket_to_channel = dict()

	def _bucket_key(self, message):
		return (message.guild.id, message.author.id, message.content)

	def update_rate_limit(self, message, current=None):
		bucket = self.get_bucket(message, current)

		current_channel_id = message.channel.id
		prev_channel_id = self.bucket_to_channel.get(bucket, None)

		self.bucket_to_channel[bucket] = current_channel_id

		ret = bucket.update_rate_limit(current)

		if prev_channel_id is not None and current_channel_id != prev_channel_id:
			for _ in range(OTHER_CHANNEL_PENALTY):
				ret = bucket.update_rate_limit(current)
				if ret is not None:
					break

		return ret


class SecurityConfigRecord(ConfigTableRecord):
	spam_cooldown = None
	mention_cooldown = None
	content_cooldown = None

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.create_spam_cooldown()
		self.create_mention_cooldown()
		self.create_content_cooldown()

	@property
	def guild(self):
		return self._config.bot.get_guild(self.guild_id)

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
			self.spam_count, self.spam_per, commands.BucketType.member
		)

	def create_mention_cooldown(self):
		self.mention_cooldown = commands.CooldownMapping.from_cooldown(
			self.mention_count, self.mention_per, commands.BucketType.member
		)

	def create_content_cooldown(self):
		self.content_cooldown = CooldownByContent.from_cooldown(
			5, 32.0, commands.BucketType.member
		)


class EventTimer(DatabaseTimer):
	async def get_record(self):
		return await self.bot.db.fetchrow(
			'SELECT * FROM mod_timer WHERE duration IS NOT NULL AND created_at + duration < $1 AND completed = FALSE '
			'ORDER BY created_at + duration LIMIT 1',
			datetime.utcnow() + self.MAX_SLEEP
		)

	async def cleanup_record(self, record):
		await self.bot.db.execute('UPDATE mod_timer SET completed=TRUE WHERE id=$1', record.get('id'))

	def when(self, record):
		return record.get('created_at') + record.get('duration')


# ripped from RoboDanny
class BannedMember(commands.Converter):
	async def convert(self, ctx, argument):
		ban_list = [ban async for ban in ctx.guild.bans()]

		try:
			member_id = int(argument, base=10)
			entity = disnake.utils.find(lambda u: u.user.id == member_id, ban_list)
		except ValueError:
			entity = disnake.utils.find(lambda u: str(u.user) == argument, ban_list)

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

		asyncio.create_task(self.check_tempbans())

	@commands.Cog.listener()
	async def on_log(self, guild, subject, action=None, severity=Severity.LOW, message=None, **fields):
		conf = await self.config.get_entry(guild.id)

		log_channel = conf.log_channel
		if log_channel is None:
			return

		desc = 'NAME: ' + str(subject)
		if getattr(subject, 'nick', None) is not None:
			desc += '\nNICK: ' + subject.nick
		desc += '\nMENTION: ' + subject.mention
		desc += '\nID: ' + str(subject.id)

		color = SeverityColors[severity.name].value

		e = disnake.Embed(
			title=action or 'INFO',
			description=desc,
			color=color,
			timestamp=datetime.utcnow()
		)

		for name, value in fields.items():
			e.add_field(name=name.title(), value=value, inline=False)

		e.set_thumbnail(url=subject.display_avatar.url)

		e.set_footer(text=severity.name)

		if message is not None:
			e.add_field(name='Context', value='[Click here]({})'.format(message.jump_url), inline=False)

		await log_channel.send(embed=e)

	def _craft_user_data(self, member: disnake.Member):
		data = dict(
			name=member.name,
			nick=member.nick,
			discriminator=member.discriminator,
			avatar_url=member.display_avatar.url,
		)

		return dumps(data)

	@commands.command()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True)
	async def ban(self, ctx, member: disnake.Member, *, reason: reason_converter = None):
		'''Ban a member. Requires Ban Members perms.'''

		try:
			await member.ban(reason=reason, clean_history_duration=0)
		except disnake.HTTPException:
			raise commands.CommandError('Failed banning member.')

		await ctx.send('{0} banned.'.format(str(member)))

	@commands.command()
	@can_prompt()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True)
	async def unban(self, ctx, member: BannedMember, *, reason: reason_converter = None):
		'''Unban a member. Requires Ban Members perms.'''

		if member.reason is None:
			prompt = 'No reason provided with the previous ban.'
		else:
			prompt = 'Ban reason:\n{0}'.format(member.reason)

		res = await ctx.prompt(title='Unban {0}?'.format(member.user), prompt=prompt)

		if not res:
			return

		try:
			await ctx.guild.unban(member.user, reason=reason)
		except disnake.HTTPException:
			raise commands.CommandError('Failed unbanning member.')

		await ctx.send('{0} unbanned.'.format(str(member.user)))

	@commands.command()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True, embed_links=True)
	async def tempban(self, ctx, member: Union[disnake.Member, BannedMember], amount: TimeMultConverter, unit: TimeDeltaConverter, *,
		reason: reason_converter = None):
		'''Temporarily ban a member. Requires Ban Members perms.'''

		now = datetime.utcnow()
		duration = amount * unit
		until = now + duration

		on_guild = isinstance(member, disnake.Member)

		if on_guild:
			if await ctx.is_mod(member):
				raise commands.CommandError('Can\'t tempban this member.')
		else:
			user: disnake.User = member.user
			member = FakeUser(user.id, ctx.guild, name=user.name, avatar_url=str(user.display_avatar), discriminator=user.discriminator)

		is_tempbanned = await self.bot.db.fetchval(
			'SELECT id FROM mod_timer WHERE guild_id=$1 AND user_id=$2 AND event=$3 AND completed=FALSE',
			ctx.guild.id, member.id, 'BAN'
		)

		if is_tempbanned:
			raise commands.CommandError('This member is already tempbanned. Use `alterban` to change duration?')

		if duration > MAX_DELTA:
			raise commands.CommandError('Can\'t tempban for longer than {0}. Please `ban` instead.'.format(pretty_timedelta(MAX_DELTA)))

		pretty_duration = pretty_timedelta(duration)

		# only send DMs for initial bans
		if on_guild:
			ban_msg = 'You have received a ban lasting {0} from {1}.\n\nReason:\n```\n{2}\n```'.format(
				pretty_duration, ctx.guild.name, reason
			)

			try:
				await member.send(ban_msg)
			except disnake.HTTPException:
				pass

		# reason we start a transaction is so it auto-rollbacks if the CommandError on ban fails is raised
		async with self.db.acquire() as con:
			async with con.transaction():
				try:
					await self.db.execute(
						'INSERT INTO mod_timer (guild_id, user_id, mod_id, event, created_at, duration, reason, userdata)'
						'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
						ctx.guild.id, member.id, ctx.author.id, 'BAN', now, duration, reason, self._craft_user_data(member)
					)
				except UniqueViolationError:
					# this *should* never happen but I'd rather leave it in
					raise commands.CommandError('Member is already tempbanned.')

				try:
					await ctx.guild.ban(member, clean_history_duration=0, reason=reason)
				except disnake.HTTPException:
					raise commands.CommandError('Failed tempbanning member.')

		self.event_timer.maybe_restart(until)

		try:
			await ctx.send('{0} tempbanned for {1}.'.format(str(member), pretty_duration))
		except disnake.HTTPException:
			pass

		self.bot.dispatch(
			'log', ctx.guild, member, action='TEMPBAN', severity=Severity.HIGH, message=ctx.message,
			responsible=po(ctx.author), duration=pretty_duration, reason=reason
		)

	@commands.command()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True, embed_links=True)
	async def alterban(self, ctx: AceContext, member: BannedMember, amount: TimeMultConverter, *, unit: TimeDeltaConverter):
		'''Set a new duration for a tempban.'''

		duration = amount * unit

		if duration > MAX_DELTA:
			raise commands.CommandError('Can\'t tempban for longer than {0}. Please `ban` instead.'.format(pretty_timedelta(MAX_DELTA)))

		record = await self.bot.db.fetchrow(
			'SELECT * FROM mod_timer WHERE guild_id=$1 AND user_id=$2 AND event=$3 AND completed=FALSE',
			ctx.guild.id, member.user.id, 'BAN'
		)

		if record is None:
			raise commands.CommandError('Could not find a tempban referencing this member.')

		now = datetime.utcnow()
		old_now = record.get('created_at')
		old_duration = record.get('duration')
		new_until = old_now + duration
		old_until = old_now + old_duration

		if duration == old_duration:
			raise commands.CommandError('New ban duration is the same as the current duration.')

		old_duration_pretty = pretty_timedelta(old_duration)
		old_end_pretty = pretty_timedelta(old_until - now)
		duration_pretty = pretty_timedelta(duration)

		prompt = f'The previous ban duration was {old_duration_pretty} and will end in {old_end_pretty}.\n\n'

		if new_until < now:
			prompt += 'The new duration ends in the past and will cause an immediate unban.'
		else:
			prompt += f'The new ban duration is {duration_pretty} and will end in {pretty_timedelta(new_until - now)}.'

		should_continue = await ctx.prompt(
			title='Are you sure you want to alter this tempban?',
			prompt=prompt
		)

		if not should_continue:
			return

		await self.db.execute(
			'UPDATE mod_timer SET duration=$1 WHERE guild_id=$2 AND user_id=$3 AND event=$4',
			duration, ctx.guild.id, member.user.id, 'BAN'
		)

		self.event_timer.restart_task()

		self.bot.dispatch(
			'log', ctx.guild, member.user, action='TEMPBAN UPDATE', severity=Severity.HIGH, message=ctx.message,
			responsible=po(ctx.author), duration=duration_pretty, reason=f'Previous duration was {old_duration_pretty}'
		)

	async def do_action(self, message, action, reason, clean_history_duration=0):
		'''Called when an event happens.'''

		member: disnake.Member = message.author
		guild: disnake.Guild = message.guild

		ctx = await self.bot.get_context(message, cls=AceContext)

		# ignore if member is mod
		if await ctx.is_mod():
			self.bot.dispatch(
				'log', guild, member, action='IGNORED {0} (MEMBER IS MOD)'.format(action.name), severity=Severity.LOW, message=message,
				reason=reason,
			)

			return

		role_ids = list(LEVEL_ROLE_IDS.values())[3:]
		if any(role.id in role_ids for role in message.author.roles):
			self.bot.dispatch(
				'log', guild, member, action='IGNORED {0} (MEMBER IS LEVEL 16+)'.format(action.name), severity=Severity.LOW, message=message,
				reason=reason,
			)

			return

		# otherwise, check against security actions and perform punishment
		try:
			if action is SecurityAction.TIMEOUT:
				await member.timeout(until=datetime.utcnow() + timedelta(days=28), reason=reason)
			elif action is SecurityAction.KICK:
				await member.kick(reason=reason)
			elif action is SecurityAction.BAN:
				await member.ban(clean_history_duration=clean_history_duration, reason=reason)

		except Exception as exc:
			# log error if something happened
			self.bot.dispatch(
				'log', guild, member, action='{0} FAILED'.format(action.name), severity=Severity.HIGH, message=message,
				reason=reason, error=str(exc)
			)
			return

		# log successful security event
		self.bot.dispatch(
			'log', guild, member, action=action.name, severity=Severity(action.value), message=message,
			reason=reason
		)

		try:
			await message.channel.send('{0} {1}: {2}'.format(
				po(member), SecurityVerb[action.name].value, reason
			))
		except disnake.HTTPException:
			pass

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
					message, SecurityAction[mc.spam_action], reason='Member is spamming messages'
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
					message, SecurityAction[mc.mention_action], reason='Member is spamming mentions'
				)

		if message.guild.id == AHK_GUILD_ID:
			async with CONTENT_LOCK:
				res = mc.content_cooldown.update_rate_limit(message)

				# since we're using the bucket key (guild_id, author_id, message_content)
				# we can just as well reset the bucket after a ban
				if res is not None:
					mc.content_cooldown._cache[mc.content_cooldown._bucket_key(message)].reset()

			if res is not None:
				await self.do_action(
					message, SecurityAction.BAN, reason='Member is spamming (with cleanup)', clean_history_duration=timedelta(days=1)
				)

	@commands.Cog.listener()
	async def on_event_complete(self, record):
		# relatively crucial that the bot is ready before we launch any events like tempban completions
		await self.bot.wait_until_ready()

		event = record.get('event')

		if event == 'BAN':
			await self.ban_complete(record)

	def fakeuser_from_record(self, record, guild):
		return FakeUser(record.get('user_id'), guild, **loads(record.get('userdata')))

	async def ban_complete(self, record):
		guild_id = record.get('guild_id')
		mod_id = record.get('mod_id')
		duration = record.get('duration')
		reason = record.get('reason')

		guild = self.bot.get_guild(guild_id)
		if guild is None:
			return

		mod = guild.get_member(mod_id)
		pretty_mod = '(ID: {0})'.format(str(mod_id)) if mod is None else po(mod)

		member = self.fakeuser_from_record(record, guild)

		try:
			await guild.unban(member, reason='Completed tempban issued by {0}'.format(pretty_mod))
		except disnake.HTTPException:
			return  # rip :)

		self.bot.dispatch(
			'log', guild, member, action='TEMPBAN COMPLETED', severity=Severity.RESOLVED,
			responsible=pretty_mod, duration=pretty_timedelta(duration), reason=reason
		)

	async def check_tempbans(self):
		'''Check for newly unbanned members on guild startup, and end tempbans if so'''

		await self.bot.wait_until_ready()

		tempbans = await self.db.fetch("SELECT * FROM mod_timer WHERE event='BAN' AND completed=FALSE")
		guild_bans = dict()

		for guild_id in set(tempban.get('guild_id') for tempban in tempbans):
			guild = self.bot.get_guild(guild_id)
			if guild is None:
				continue

			try:
				bans = [ban async for ban in guild.bans()]
			except disnake.HTTPException:
				continue

			guild_bans[guild_id] = (guild, [ban.user.id for ban in bans])

		for tempban in tempbans:
			guild_id = tempban.get('guild_id')

			info = guild_bans.get(guild_id, None)
			if info is None:
				continue  # not in guild (or could not fetch banlist), in which case just ignore and let the unban event fail whenever

			guild, banned_ids = info

			user_id = tempban.get('user_id')

			# if this user is not banned anymore, run the on_member_unban event to clear the tempban
			if user_id not in banned_ids:
				await self.on_member_unban(guild, self.fakeuser_from_record(tempban, guild))

	@commands.Cog.listener()
	async def on_member_unban(self, guild, user):
		# complete tempbans if user is manually unbanned
		_id = await self.db.fetchval(
			'UPDATE mod_timer SET completed=TRUE WHERE guild_id=$1 AND user_id=$2 AND event=$3 AND completed=FALSE RETURNING id',
			guild.id, user.id, 'BAN'
		)

		# also restart timer if the next in line *was* that tempban
		if _id is not None:
			self.event_timer.restart_if(lambda r: r.get('id') == _id)

			self.bot.dispatch(
				'log', guild, user, action='TEMPBAN CANCELLED', severity=Severity.RESOLVED,
				reason='Tempbanned member manually unbanned.'
			)

	@commands.command()
	@commands.has_permissions(manage_messages=True)
	@commands.bot_has_permissions(manage_messages=True)
	async def clear(self, ctx, message_count: int, user: MaybeMemberConverter = None):
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
			return msg.author.id == user.id and all_check(msg)

		try:
			await ctx.message.delete()
		except disnake.HTTPException:
			pass

		try:
			deleted = await ctx.channel.purge(limit=message_count, check=all_check if user is None else user_check)
		except disnake.HTTPException:
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
		Amount of messages the bot will check for deletion.

		--max <int>
		Maximum amount of messages the bot will delete.

		--bot
		Only delete messages from bots.

		--user member [...]
		Only delete messages from these members.

		--after message_id
		Start deleting after this message id.

		--before message_id
		Delete, at most, up until this message id.

		--contains <string> [...]
		Delete messages containing this string(s).

		--starts <string> [...]
		Delete messages starting with this string(s).

		--ends <string> [...]
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
			converter = MaybeMemberConverter()
			members = []

			for id in args.user:
				try:
					member = await converter.convert(ctx, id)
					members.append(member)
				except commands.CommandError:
					raise commands.CommandError('Unknown user: "{0}"'.format(id))

			# yes, if both objects were disnake.Member I could do m.author in members,
			# but since member can be FakeUser I need to do an explicit id comparison
			preds.append(lambda m: any(m.author.id == member.id for member in members))

		if args.contains:
			preds.append(lambda m: any((s.lower() in m.content.lower()) for s in args.contains))

		if args.bot:
			preds.append(lambda m: m.author.bot)

		if args.starts:
			preds.append(lambda m: any(m.content.lower().startswith(s.lower()) for s in args.starts))

		if args.ends:
			preds.append(lambda m: any(m.content.lower().endswith(s.lower()) for s in args.ends))

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
			after = disnake.Object(id=args.after)
			limit = PURGE_LIMIT

		if args.before:
			before = disnake.Object(id=args.before)

		# if we actually want to manually specify it doe
		if args.check is not None:
			limit = max(0, min(PURGE_LIMIT, args.check))

		try:
			deleted_messages = await ctx.channel.purge(limit=limit, check=predicate, before=before, after=after)
		except disnake.HTTPException:
			raise commands.CommandError('Error occurred when deleting messages.')

		deleted_count = len(deleted_messages)

		log.info('%s purged %s messages in %s', po(ctx.author), deleted_count, po(ctx.guild))

		await ctx.send('{0} messages deleted.'.format(deleted_count), delete_after=10)

	@commands.command()
	@is_mod()
	async def logchannel(self, ctx, *, channel: disnake.TextChannel = None):
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
	async def perms(self, ctx, user: disnake.Member = None, channel: disnake.TextChannel = None):
		'''Lists a users permissions in a channel.'''

		if user is None:
			user = ctx.author

		if channel is None:
			channel = ctx.channel

		perms = channel.permissions_for(user)

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

		perms: disnake.Permissions = ctx.perms

		if action == 'TIMEOUT' and not perms.moderate_members:
			data += '\n\nNOTE: I do not have Time out members permissions!'
		elif action == 'BAN' and not perms.ban_members:
			data += '\n\nNOTE: I do not have Ban members permissions!'
		elif action == 'KICK' and not perms.kick_members:
			data += '\n\nNOTE: I do not have Kick members permissions!'
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
		'''Set action taken towards spamming members. Valid actions are `TIMEOUT`, `KICK`, and `BAN`. Leave argument blank to disable anti-spam.'''

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
		'''Action taken towards mention-spamming members. Valid actions are `TIMEOUT`, `KICK`, and `BAN`. Leave argument blank to disable anti-mention.'''

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

	@commands.command(aliases=['pc'], hidden=True)
	@is_mod()
	@commands.bot_has_permissions(attach_files=True)
	async def permcheck(self, ctx):
		'''Checks for potentially dangerous permissions.'''

		guild: disnake.Guild = ctx.guild
		roles = guild.roles
		categories = guild.categories
		text_channels = guild.text_channels

		out = ''
		nl = '\n'

		# roles

		rp = defaultdict(list)

		for r in roles:
			r: disnake.Role

			# find dangerous perms
			for dangerous_permission in MOD_PERMS:
				if getattr(r.permissions, dangerous_permission):
					rp[r].append('- ' + dangerous_permission)
					if dangerous_permission == 'administrator':
						break

		for role, perms in rp.items():
			out += f'ROLE {role.name}\n{nl.join(perms)}\n\n'

		# categories

		catp = defaultdict(list)

		for cat in categories:
			cat: disnake.CategoryChannel

			# ignore channel if there is no overwrites
			# so, turns out, if you create a new category and don't touch the permissions,
			# the overwrites entry for the default_role will not be there.
			# so a category (or channel) with zero overwrites can either have an empty overwrites map,
			# or one of size one with the default_role entry with value 0
			if len(cat.overwrites) <= 1 and all(overwrite.is_empty() for overwrite in cat.overwrites.values()):
				continue

			# if there are overwrites but no synced channels, notify of this
			if not any(c.permissions_synced for c in cat.text_channels):
				out += f'CATEGORY {cat.name}\n+ This category has overwrites but no synced channels!\n\n'
				continue

			# find dangerous perms for each role
			for role, permissions in cat.overwrites.items():
				if role is not guild.default_role and permissions.is_empty():
					catp[(cat, role)].append('+ Value of zero (does nothing)')
				else:
					for dangerous_permission in MOD_PERMS:
						if getattr(permissions, dangerous_permission):
							catp[(cat, role)].append('- ' + dangerous_permission)
							if dangerous_permission == 'administrator':
								break

		for (cat, role), perms in catp.items():
			out += f'CATEGORY {cat.name} ROLE {role.name}\n{nl.join(perms)}\n\n'

		# channels (non-synced, anyway)

		cp = defaultdict(list)

		for c in text_channels:
			c: disnake.TextChannel

			# if this channel has synced permissions it should have been handled by the category check
			# also if it's not a text channel I don't care about it
			if c.permissions_synced or not isinstance(c, disnake.TextChannel):
				continue

			# etc
			for role, permissions in c.overwrites.items():
				if role is not guild.default_role and permissions.is_empty():
					cp[(c, role)].append('+ Value of zero (does nothing)')
				for dangerous_permission in MOD_PERMS:
					if getattr(permissions, dangerous_permission):
						cp[(c, role)].append('- ' + dangerous_permission)
						if dangerous_permission == 'administrator':
							break

		for (chan, role), perms in cp.items():
			out += f'CHANNEL {chan.name} ROLE {role.name}\n{nl.join(perms)}\n\n'

		out = out.strip()

		if not out:
			await ctx.send('No potentially dangerous permissions found.')
			return

		if len(out) > 2000:
			fp = io.BytesIO(out.encode('utf-8'))
			await ctx.send(file=disnake.File(fp, 'perms.diff'))
		else:
			await ctx.send(f'```diff\n{out}\n```')


def setup(bot):
	bot.add_cog(Moderation(bot))
