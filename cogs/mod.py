import discord
import logging
import asyncpg

from discord.ext import commands
from datetime import datetime, timedelta

from cogs.mixins import AceMixin
from cogs.ahk.ids import RULES_MSG_ID
from utils.databasetimer import DatabaseTimer
from utils.time import pretty_datetime, pretty_timedelta, TimeMultConverter, TimeDeltaConverter
from utils.context import is_mod
from utils.fakemember import FakeMember
from utils.string import po

log = logging.getLogger(__name__)

MAX_DELTA = timedelta(days=365 * 10)
OK_EMOJI = '\U00002705'

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


# stolen from Rapptz, thanks :ok_hand:
class BannedMember(commands.Converter):
	async def convert(self, ctx, argument):
		ban_list = await ctx.guild.bans()
		try:
			member_id = int(argument, base=10)
			entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
		except ValueError:
			entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)

		if entity is None:
			raise commands.BadArgument("Not a valid previously-banned member.")
		return entity


class Moderator(AceMixin, commands.Cog):
	'''Simple moderation commands.'''

	def __init__(self, bot):
		super().__init__(bot)

		self.ban_timer = DatabaseTimer(self.bot, 'banned', 'until', 'ban_complete')
		self.mute_timer = DatabaseTimer(self.bot, 'muted', 'until', 'mute_complete')

	def _issuer_text(self, guild, user_id):
		if isinstance(user_id, discord.Member):
			mod = user_id
		else:
			mod = guild.get_member(user_id)

		if mod is None:
			return '(ID: {})'.format(user_id)
		else:
			return '{} (ID: {})'.format(mod.display_name, mod.id)

	@commands.Cog.listener()
	async def on_ban_complete(self, record):
		guild = self.bot.get_guild(record.get('guild_id'))
		if guild is None:
			return

		issuer = self._issuer_text(guild, record.get('mod_id'))
		reason = 'Completed tempban issued by {0}'.format(issuer)

		user_id = record.get('user_id')

		await guild.unban(discord.Object(user_id), reason=reason)

		self.bot.dispatch(
			'log',
			FakeMember(id=user_id, name=record.get('name'), avatar_url=record.get('avatar_url'), guild=guild),
			action='UNBAN',
			reason=reason,
			severity=2
		)

	@commands.Cog.listener()
	async def on_mute_complete(self, record):
		conf = await self.bot.config.get_entry(record.get('guild_id'))
		mute_role = conf.mute_role

		if mute_role is None:
			return

		guild = self.bot.get_guild(record.get('guild_id'))
		if guild is None:
			return

		member = guild.get_member(record.get('user_id'))
		if member is None:
			return

		issuer = self._issuer_text(guild, record.get('mod_id'))
		reason = 'Completed tempmute issued by {0}'.format(issuer)

		await member.remove_roles(mute_role, reason=reason)

		self.bot.dispatch('log', member, action='UNMUTE', reason=reason, severity=0)

	@commands.command()
	@commands.has_permissions(manage_roles=True)
	@commands.bot_has_permissions(manage_roles=True, embed_links=True)
	async def tempmute(self, ctx, member: discord.Member, amount: TimeMultConverter, unit: TimeDeltaConverter, *, reason=None):
		'''Temporarily mute a member. Manage roles permissions required.'''

		reason = reason or 'No reason provided.'
		now = datetime.utcnow()
		delta = amount * unit
		until = now + delta

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t mute this member.')

		if delta > MAX_DELTA:
			raise commands.CommandError('Can\'t tempmute for longer than {}. Use `mute` instead.'.format(
				pretty_timedelta(MAX_DELTA))
			)

		conf = await self.bot.config.get_entry(ctx.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			raise commands.CommandError('Mute role not set or not found.')

		await self.db.execute(
			'INSERT INTO muted (guild_id, user_id, mod_id, until) VALUES ($1, $2, $3, $4) '
			'ON CONFLICT (guild_id, user_id) DO UPDATE SET mod_id=$3, until=$4',
			ctx.guild.id, member.id, ctx.author.id, until
		)

		try:
			await member.add_roles(mute_role)
		except discord.HTTPException:
			raise commands.CommandError('Failed adding mute role.')

		e = discord.Embed(
			description='{0.display_name} muted for {1}.'.format(member, pretty_timedelta(delta)),
		)

		e.add_field(name='Reason', value=reason)

		try:
			await ctx.send(embed=e)
		except discord.HTTPException:
			pass

		self.mute_timer.maybe_restart(until)

		full_reason = 'Issued by: {}\nDuration: {}\n\nMeta-reason:\n```\n{}\n```'.format(
			self._issuer_text(ctx.guild, ctx.author), pretty_timedelta(delta), reason
		)

		self.bot.dispatch('log', member, action='MUTE', reason=full_reason, severity=0)

		log.info('{} issued a {} tempmute for {} in {}. Reason: {}'.format(
			po(ctx.author),
			pretty_timedelta(delta),
			po(member),
			po(ctx.guild),
			reason
		))

	@commands.command()
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True, embed_links=True)
	async def tempban(self, ctx, member: discord.Member, amount: TimeMultConverter, unit: TimeDeltaConverter, *, reason=None):
		'''Tempban a member. Ban permissions required.'''

		reason = reason or 'No reason provided.'
		now = datetime.utcnow()
		delta = amount * unit
		until = now + delta

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t tempban this member.')

		if delta > MAX_DELTA:
			raise commands.CommandError('Can\'t tempban for longer than {}.'.format(pretty_timedelta(MAX_DELTA)))

		ban_msg = 'You have been banned from {} until the {}.\n\nReason:\n```\n{}\n```'.format(
			ctx.guild.name, pretty_datetime(until), reason
		)

		try:
			await member.send(ban_msg)
			send_success = True
		except discord.HTTPException:
			# can't send, not much we can do about it
			send_success = False

		try:
			await ctx.guild.ban(member, delete_message_days=0, reason=reason)
		except discord.HTTPException as exc:
			raise commands.CommandError('Ban failed:\n{}'.format(exc))

		await self.db.execute(
			'INSERT INTO banned (guild_id, user_id, mod_id, until, name, avatar_url) VALUES ($1, $2, $3, $4, $5, $6)',
			ctx.guild.id, member.id, ctx.author.id, until, member.display_name, str(member.avatar_url)
		)

		self.ban_timer.maybe_restart(until)

		e = discord.Embed(
			description='{0.display_name} banned for {1}.'.format(member, pretty_timedelta(delta)),
		)

		e.add_field(name='Reason', value=reason)

		try:
			await ctx.send(embed=e)
		except discord.HTTPException:
			pass

		issuer = self._issuer_text(ctx.guild, ctx.author)
		full_reason = 'Issued by: {}\nDuration: {}\nUser messaged: {}\n\nMeta-reason:\n```\n{}\n```'.format(
			issuer, pretty_timedelta(delta), 'yes' if send_success else 'no', reason
		)

		self.bot.dispatch('log', member, action='TEMPBAN', reason=full_reason, severity=2)

		log.info('{} issued a {} tempban for {} in {}. Reason: {}'.format(
			po(ctx.author),
			pretty_timedelta(delta),
			po(member),
			po(ctx.guild),
			reason
		))

	@commands.command()
	@commands.has_permissions(kick_members=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def mute(self, ctx, *, member: discord.Member):
		'''Mute a member. Kick permissions required.'''

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t mute this member.')

		conf = await self.bot.config.get_entry(ctx.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			raise commands.CommandError('Mute role not set or not found.')

		if mute_role in member.roles:
			raise commands.CommandError('Member already muted.')

		reason = 'Muted by {0.display_name} (ID: {0.id})'.format(ctx.author)

		await member.add_roles(mute_role, reason=reason)

		try:
			await ctx.send('{0.display_name} muted.'.format(member))
		except discord.HTTPException:
			pass

		self.bot.dispatch('log', member, action='MUTE', reason=reason)

		log.info('{} issued a mute on {} in {}. Reason: {}'.format(
			po(ctx.author),
			po(member),
			po(ctx.guild),
			reason
		))

	@commands.command()
	@commands.has_permissions(kick_members=True)
	@commands.bot_has_permissions(manage_roles=True)
	async def unmute(self, ctx, *, member: discord.Member):
		'''Unmute a member. Kick permissions required.'''

		if await ctx.is_mod(member):
			raise commands.CommandError('Can\'t unmute this member.')

		conf = await self.bot.config.get_entry(ctx.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			raise commands.CommandError('Mute role not set or not found.')

		if mute_role not in member.roles:
			raise commands.CommandError('Member not previously muted.')

		reason = 'Unmuted by {0.mention} (ID: {0.id})'.format(ctx.author)

		await member.remove_roles(mute_role, reason=reason)

		try:
			await ctx.send('{0.display_name} unmuted.'.format(member))
		except discord.HTTPException:
			pass

		self.bot.dispatch('log', member, action='UNMUTE', reason=reason, severity=0)

		log.info('{} issued an unmute on {} in {}.'.format(
			po(ctx.author),
			po(member),
			po(ctx.guild)
		))

	@commands.Cog.listener()
	async def on_member_unban(self, guild, member):
		_id = await self.db.fetchval(
			'DELETE FROM banned WHERE guild_id=$1 AND user_id=$2 RETURNING id',
			guild.id, member.id
		)

		if _id is not None:
			self.ban_timer.restart_if(lambda r: r.get('id') == _id)

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		# detect if the muted role was added or removed
		# this is purely to keep the database updated.

		br = set(before.roles)
		ar = set(after.roles)

		if br == ar:
			return

		conf = await self.bot.config.get_entry(before.guild.id)
		mute_role = conf.mute_role

		if mute_role is None:
			return

		if mute_role in br - ar:
			_id = await self.db.fetchval(
				'DELETE FROM muted WHERE guild_id=$1 AND user_id=$2 RETURNING id',
				before.guild.id, before.id
			)

			self.mute_timer.restart_if(lambda r: r.get('id') == _id)

		elif mute_role in ar - br:
			try:
				await self.db.execute(
					'INSERT INTO muted (guild_id, user_id) VALUES ($1, $2)',
					before.guild.id, before.id
				)
			except asyncpg.UniqueViolationError:
				pass

	@commands.Cog.listener()
	async def on_member_join(self, member):
		if member.bot:
			return

		conf = await self.bot.config.get_entry(member.guild.id)
		mute_role = conf.mute_role

		if mute_role is not None:

			# check if member was previously muted
			already_muted = await self.db.fetchval(
				'SELECT id FROM muted WHERE guild_id=$1 AND user_id=$2',
				member.guild.id, member.id
			)

			if already_muted:
				reason = 'Re-muting newly joined member who was previously muted'
				await member.add_roles(mute_role, reason=reason)
				self.bot.dispatch('log', member, action='MUTE', reason=reason, severity=0)

	@commands.command()
	@commands.has_permissions(manage_messages=True)
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

		try:
			await ctx.message.delete()
		except discord.HTTPException:
			pass

		try:
			deleted = await ctx.channel.purge(limit=message_count, check=all_check if user is None else user_check)
		except discord.HTTPException:
			raise commands.CommandError('Failed deleting messages. Does the bot have the necessary permissions?')

		count = len(deleted)

		log.info('{} deleted {} messages in {}'.format(
			po(ctx.author), count, po(ctx.guild)
		))

		await ctx.send(f'Deleted {count} message{"s" if count > 1 else ""}.', delete_after=5)

	@commands.command()
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


def setup(bot):
	bot.add_cog(Moderator(bot))
