import discord
import asyncio
import re
import logging

from discord.ext import commands, tasks
from enum import Enum, IntEnum
from datetime import datetime
from asyncpg.exceptions import UniqueViolationError

from cogs.mixins import AceMixin
from cogs.ahk.ids import AHK_GUILD_ID
from utils.converters import TimeMultConverter, TimeDeltaConverter
from utils.time import pretty_timedelta
from utils.checks import is_mod_pred
from utils.severity import SeverityColors


ALLOWED_GUILDS = (115993023636176902, 517692823621861407)
SUBMODULES = ('join', 'mention', 'spam')
LOCK = asyncio.Lock()
SPAM_LOCK = asyncio.Lock()
MENTION_LOCK = asyncio.Lock()

log = logging.getLogger(__name__)


def message_link(message):
	return f'https://discordapp.com/channels/{message.guild.id}/{message.channel.id}/{message.id}'


class PatternConverter(commands.Converter):
	async def convert(self, ctx, pattern):
		'''Tests if the pattern is valid.'''

		try:
			re.compile(pattern)
		except re.error:
			raise commands.CommandError('Pattern is not valid RegEx.')

		return pattern


class SubmoduleConverter(commands.Converter):
	async def convert(self, ctx, module):
		module = module.lower()
		if module not in SUBMODULES:
			raise commands.CommandError(f'\'{module}\' is not a valid module.')
		return module


class ActionConverter(commands.Converter):
	async def convert(self, ctx, action):
		action = action.lower()

		for member in SecurityAction:
			if member.name.lower() == action:
				return member

		raise commands.CommandError(f'\'{action}\' is not a valid action.')


class CountConverter(commands.Converter):
	async def convert(self, ctx, count):
		count = int(count)

		if count < 3:
			raise commands.CommandError('Setting count less than 3 is not recommended.')

		return count


class PerConverter(commands.Converter):
	async def convert(self, ctx, per):
		per = float(per)

		if per < 3.0:
			raise commands.CommandError('Setting per less than 3 is not recommended.')
		elif per > 30.0:
			raise commands.CommandError('Setting per more than 30 is not recommended.')

		return per


class SecurityAction(IntEnum):
	MUTE = 0
	KICK = 1
	BAN = 2


from datetime import timedelta

from utils.config import ConfigTable, SecurityConfigEntry


class Security(AceMixin, commands.Cog):
	'''Security features.

	Valid actions are: `MUTE`, `KICK` and `BAN`

	Actions are triggered when an event happens more than `COUNT` times per `PER` seconds.

	To clear a value leave all arguments blank.
	'''

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(
			bot, 'mod', 'guild_id',
			dict(
				id=int,
				guild_id=int,
				mute_role_id=int,
				log_channel_id=int,

				join_enabled=bool,
				spam_enabled=bool,
				mention_enabled=bool,

				join_action=int,
				join_age=timedelta,
				join_ignore_age=timedelta,
				join_kick_cooldown=timedelta,

				spam_action=int,
				spam_count=int,
				spam_per=float,

				mention_action=int,
				mention_count=int,
				mention_per=float,

			),
			entry_class=SecurityConfigEntry
		)

		self.last_pattern_kick = dict()  # (guild_id, user_id): datetime
		self.setup_configs.start()

	# init configs
	@tasks.loop(count=1)
	async def setup_configs(self):
		recs = await self.db.fetch('SELECT guild_id FROM mod')
		for rec in recs:
			await self.get_config(rec.get('guild_id'))

	async def get_config(self, guild_id):
		# security stuff is only for the ahk guild as of right now
		if guild_id not in ALLOWED_GUILDS:
			raise commands.CommandError('This feature is current reserved for selected guilds, sorry.')

		return await self.config.get_entry(guild_id)

	async def log(self, action=None, reason=None, severity=None, author=None, channel=None, message=None):
		if channel is None:
			return

		severity = severity or SeverityColors.LOW

		e = discord.Embed(
			title=action or 'INFO',
			description=author.mention + ' ' + reason,
			color=severity.value,
			timestamp=datetime.utcnow()
		)

		e.set_author(name=author.display_name, icon_url=author.avatar_url)
		e.set_footer(text='{} - ID: {}'.format(severity.name, author.id))

		if message is not None:
			e.description += '\n\n[Context here]({})'.format(message_link(message))

		await channel.send(embed=e)

	async def _do_action(self, mc, member, action, reason=None, message=None):
		'''Called when an event happens.'''
		try:
			if action is SecurityAction.MUTE:
				if mc.mute_role is None:
					raise ValueError('No mute role set.')

				try:
					await self.db.execute(
						'INSERT INTO muted (guild_id, user_id) VALUES ($1, $2)', member.guild.id, member.id
					)
				except UniqueViolationError:
					pass

				await member.add_roles(mc.mute_role, reason=reason)

			elif action is SecurityAction.KICK:
				await member.kick(reason=reason)

			elif action is SecurityAction.BAN:
				await member.ban(reason=reason)

		except Exception as exc:
			await self.log(
				channel=mc.log_channel, author=member, action='{} FAILED'.format(action.name), reason=str(exc),
				severity=SeverityColors.HIGH, message=message
			)

			return

		await self.log(
			channel=mc.log_channel, author=member, action=action.name, reason=reason,
			severity=dict(MUTE=SeverityColors.LOW, KICK=SeverityColors.MEDIUM, BAN=SeverityColors.HIGH)[action.name],
			message=message
		)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None:
			return

		if message.guild.id not in ALLOWED_GUILDS:
			return

		if message.author.bot:
			return

		if await is_mod_pred(message):
			return

		mc = await self.get_config(message.guild.id)

		if mc.spam_enabled:

			async with SPAM_LOCK:
				res = mc.spam_cooldown.update_rate_limit(message)
				if res is not None:
					mc.spam_cooldown._cache[mc.spam_cooldown._bucket_key(message)].reset()

			if res is not None:
				mc.spam_cooldown._cache[mc.spam_cooldown._bucket_key(message)].reset()

				await self._do_action(
					mc, message.author, SecurityAction(mc.spam_action),
					reason='Member is spamming', message=message
				)

		if mc.mention_enabled:
			for mention in message.mentions:

				async with MENTION_LOCK:
					res = mc.mention_cooldown.update_rate_limit(message)
					if res is not None:
						mc.mention_cooldown._cache[mc.mention_cooldown._bucket_key(message)].reset()

				if res is not None:
					mc.mention_cooldown._cache[mc.mention_cooldown._bucket_key(message)].reset()

					await self._do_action(
						mc, message.author, SecurityAction(mc.mention_action),
						reason='Member is spamming mentions', message=message
					)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		if member.guild.id not in ALLOWED_GUILDS:
			return

		mc = await self.get_config(member.guild.id)

		if await self.db.fetchval('SELECT id FROM muted WHERE guild_id=$1 AND user_id=$2', member.guild.id, member.id):
			reason = 'Member was previously muted.'

			if mc.mute_role is None:
				await self.log(
					action='MUTE FAILED',
					reason='Member previously muted but mute role not currently found.',
					severity=SeverityColors.LOW,
					author=member
				)
			else:
				await member.add_roles(mc.mute_role, reason=reason)

		if not mc.join_enabled:
			return

		age = datetime.utcnow() - member.created_at

		# ignore user if ignore_age is set and passed
		if mc.join_ignore_age is not None:
			if age > mc.join_ignore_age:
				return

		# do action if below minimum account age
		if mc.join_age is not None and member.created_at is not None:
			if mc.join_age > age:
				await self._do_action(
					mc, member, SecurityAction(mc.join_action),
					reason='Account age {}, which is younger than the limit of {}'.format(
						pretty_timedelta(age), pretty_timedelta(mc.join_age)
					)
				)

				return

		pats = await self.db.fetch(
			'SELECT * FROM kick_pattern WHERE guild_id=$1 AND disabled=$2',
			member.guild.id, False
		)

		# do action if matching any patterns
		for pat in pats:
			pattern = pat.get('pattern')
			if re.fullmatch(pattern, member.name):
				key = (member.guild.id, member.id)

				if key in self.last_pattern_kick and (datetime.now() - self.last_pattern_kick[key]) < mc.join_kick_cooldown:
					await self.log(
						reason='Member spared by kick pattern cooldown. Pattern: `{}`'.format(pattern),
						severity=SeverityColors.MEDIUM, author=member, channel=mc.log_channel
					)
					self.last_pattern_kick.pop(key)
					return

				await self._do_action(
					mc, member, SecurityAction(mc.join_action),
					reason='Member name matched pattern: `{}`'.format(pattern)
				)

				self.last_pattern_kick[key] = datetime.now()
				return

	@commands.Cog.listener()
	async def on_member_update(self, before, after):
		try:
			conf = await self.get_config(before.guild.id)
		except commands.CommandError:
			return

		br = set(before.roles)
		ar = set(after.roles)

		if br == ar:
			return

		if conf.mute_role in br - ar:
			await self.db.execute(
				'DELETE FROM muted WHERE guild_id=$1 AND user_id=$2',
				before.guild.id, before.id
			)
		elif conf.mute_role in ar - br:
			try:
				await self.db.execute(
					'INSERT INTO muted (guild_id, user_id) VALUES ($1, $2)',
					before.guild.id, before.id
				)
			except UniqueViolationError:
				pass

	async def cog_check(self, ctx):
		return ctx.guild.id in ALLOWED_GUILDS and await is_mod_pred(ctx)

	def _print_status(self, boolean):
		return 'ENABLED' if boolean else 'DISABLED'

	@commands.command()
	async def mute(self, ctx, *, member: discord.Member):
		'''Mute a member.'''

		mc = await self.get_config(ctx.guild.id)

		if mc.mute_role is None:
			raise commands.CommandError('No mute role set.')

		if mc.mute_role in member.roles:
			raise commands.CommandError('Member already muted.')

		reason = 'Muted by {} (ID: {})'.format(ctx.author.mention, ctx.author.id)

		try:
			await self.db.execute('INSERT INTO muted (guild_id, user_id) VALUES ($1, $2)', ctx.guild.id, member.id)
		except UniqueViolationError:
			pass

		await member.add_roles(mc.mute_role, reason=reason)

		await ctx.send('{} muted.'.format(member.name))

		await self.log(
			action='MUTE',
			reason=reason,
			severity=SeverityColors.LOW,
			author=member,
			channel=mc.log_channel,
			message=ctx.message
		)

	@commands.command()
	async def unmute(self, ctx, *, member: discord.Member):
		'''Unmute a member.'''

		mc = await self.get_config(ctx.guild.id)

		if mc.mute_role is None:
			raise commands.CommandError('No mute role set.')

		if mc.mute_role not in member.roles:
			raise commands.CommandError('Member not previously muted.')

		reason = 'Unmuted by {} (ID: {})'.format(ctx.author.mention, ctx.author.id)

		await self.db.execute('DELETE FROM muted WHERE guild_id=$1 AND user_id=$2', member.guild.id, member.id)

		await member.remove_roles(mc.mute_role, reason=reason)

		await ctx.send('{} unmuted.'.format(member.name))

		await self.log(
			action='UNMUTE',
			reason=reason,
			severity=SeverityColors.LOW,
			author=member,
			channel=mc.log_channel,
			message=ctx.message
		)

	@commands.group(aliases=['sec'], invoke_without_command=True)
	async def security(self, ctx):
		'''View and edit security settings.'''

		mc = await self.get_config(ctx.guild.id)

		desc = 'VERIFICATION LEVEL: **{}**''\nMUTE ROLE: {}\nLOG CHANNEL: {}'.format(
			str(ctx.guild.verification_level).upper(),
			mc.mute_role.mention if mc.mute_role else '**NOT SET**',
			mc.log_channel.mention if mc.log_channel else '**NOT SET**',
		)

		e = discord.Embed(description=desc)

		e.set_author(name='Security', icon_url=self.bot.user.avatar_url)
		e.add_field(name='SPAM', value=await self._spam_status(mc))
		e.add_field(name='MENTION', value=await self._mention_status(mc))
		e.add_field(name='JOIN', value=await self._join_status(mc), inline=False)

		await ctx.send(embed=e)

	@security.command()
	async def muterole(self, ctx, *, role: discord.Role):
		'''Set a role that will be given to muted members.'''

		mc = await self.get_config(ctx.guild.id)

		await mc.set('mute_role_id', role.id)
		await ctx.send('Mute role set to {} (ID: {})'.format(role.name, role.id))

	@security.command()
	async def logchannel(self, ctx, *, channel: discord.TextChannel):
		'''Set a text channel for logging incidents.'''

		mc = await self.get_config(ctx.guild.id)

		await mc.set('log_channel_id', channel.id)
		await ctx.send('Log channel set to {} (ID: {})'.format(channel.mention, channel.id))

	@security.command()
	async def enable(self, ctx, *, module: SubmoduleConverter):
		'''Enable a submodule.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set(f'{module}_enabled', True)

		if module == 'mention':
			mc.create_mention_cooldown()
		elif module == 'spam':
			mc.create_spam_cooldown()

		await ctx.send(f'\'{module.upper()}\' enabled.')

	@security.command()
	async def disable(self, ctx, *, module: SubmoduleConverter):
		'''Disable a submodule.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set(f'{module}_enabled', False)

		await ctx.send(f'\'{module.upper()}\' disabled.')

	@security.group(invoke_without_command=True)
	async def spam(self, ctx):
		'''Configure security settings related to message spam.'''

		mc = await self.get_config(ctx.guild.id)

		e = discord.Embed(description=await self._spam_status(mc))
		e.set_author(name=f'SPAM', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@spam.command(name='action')
	async def spam_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set('spam_action', action.value)

		await ctx.invoke(self.spam)

	@spam.command(name='limit')
	async def spam_limit(self, ctx, count: CountConverter, per: PerConverter):
		'''Maximum mentions allowed within the time span.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set('spam_count', count)
		await mc.set('spam_per', per)

		mc.create_spam_cooldown()

		await ctx.invoke(self.spam)

	async def _spam_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MESSAGES**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.spam_enabled),
			SecurityAction(mc.spam_action).name,
			mc.spam_count,
			mc.spam_per
		)

	@security.group(invoke_without_command=True)
	async def mention(self, ctx):
		'''Configure security settings related to mentions.'''

		mc = await self.get_config(ctx.guild.id)

		e = discord.Embed(description=await self._mention_status(mc))
		e.set_author(name=f'MENTION', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@mention.command(name='action')
	async def mention_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set('mention_action', action.value)

		await ctx.invoke(self.mention)

	@mention.command(name='limit')
	async def mention_limit(self, ctx, count: CountConverter, per: PerConverter):
		'''Maximum mentions allowed within the time span.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set('mention_count', count)
		await mc.set('mention_per', per)

		# set new cooldown
		mc.create_mention_cooldown()

		await ctx.invoke(self.mention)

	async def _mention_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MENTIONS**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.mention_enabled),
			SecurityAction(mc.mention_action).name,
			mc.mention_count,
			mc.mention_per
		)

	@security.group(invoke_without_command=True)
	async def join(self, ctx):
		'''Configure security settings related to members joining.'''

		patterns = await self.db.fetch(
			'SELECT id, pattern, disabled FROM kick_pattern WHERE guild_id=$1',
			ctx.guild.id
		)

		enabled_pats = list()
		disabled_pats = list()

		for p in patterns:
			pat_name = f'{p.get("id")}. `{p.get("pattern")}`'
			if p.get('disabled'):
				disabled_pats.append(pat_name)
			else:
				enabled_pats.append(pat_name)

		e = discord.Embed(description=await self._join_status(await self.get_config(ctx.guild.id)))

		e.add_field(name='Enabled patterns', value='\n'.join(enabled_pats) if enabled_pats else 'None')

		if disabled_pats:
			e.add_field(name='Disabled patterns', value='\n'.join(disabled_pats))

		e.set_author(name=f'JOIN', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@join.command(name='action')
	async def join_action(self, ctx, action: ActionConverter):
		'''Set an action upon disallowed member join.'''

		mc = await self.get_config(ctx.guild.id)
		await mc.set('join_action', action.value)

		await ctx.invoke(self.join)

	async def _join_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nACTIVE PATTERNS: **{}**\nKICK PATTERN COOLDOWN: **{}**\nMINIMUM AGE: **{}**\nIGNORE AFTER AGE: **{}**'.format(
			self._print_status(mc.join_enabled),
			SecurityAction(mc.join_action).name,
			await self.db.fetchval(
				'SELECT COUNT(*) FROM kick_pattern WHERE guild_id=$1 AND disabled=FALSE', mc.guild_id
			),
			'NOT SET' if mc.join_kick_cooldown is None else (pretty_timedelta(mc.join_kick_cooldown).upper()),
			'NOT SET' if mc.join_age is None else (pretty_timedelta(mc.join_age).upper()),
			'NOT SET' if mc.join_ignore_age is None else (pretty_timedelta(mc.join_ignore_age).upper()),
		)

	@join.command(name='age')
	async def join_age(self, ctx, amount: TimeMultConverter = None, unit: TimeDeltaConverter = None):
		'''Action will always perform on joins with accounts newer than this.'''

		if amount is not None and unit is None:
			raise commands.CommandError('Malformed input.')

		mc = await self.get_config(ctx.guild.id)

		if amount is None:
			await mc.set('join_age', None)
			await ctx.send('Account age limit disabled.')
			return

		delta = amount * unit

		await mc.set('join_age', delta)
		await ctx.send('New account age limit set: {}'.format(pretty_timedelta(delta)))

	@join.command(name='ignoreage')
	async def join_ignore_age(self, ctx, amount: TimeMultConverter = None, unit: TimeDeltaConverter = None):
		'''Action will never perform on joins with accounts older than this.'''

		if amount is not None and unit is None:
			raise commands.CommandError('Malformed input.')

		mc = await self.get_config(ctx.guild.id)

		if amount is None:
			await mc.set('join_ignore_age', None)
			await ctx.send('Ignore account age limit disabled.')
			return

		delta = amount * unit

		await mc.set('join_ignore_age', delta)
		await ctx.send('New ignore account age limit set: {}'.format(pretty_timedelta(delta)))

	@join.command(name='cooldown')
	async def join_kick_cooldown(self, ctx, amount: TimeMultConverter = None, unit: TimeDeltaConverter = None):
		'''User will not be kicked twice by kick cooldowns within this period.'''

		if amount is not None and unit is None:
			raise commands.CommandError('Malformed input.')

		mc = await self.get_config(ctx.guild.id)

		if amount is None:
			await mc.set('join_kick_cooldown', None)
			await ctx.send('Join kick pattern cooldown disabled.')
			return

		delta = amount * unit

		await mc.set('join_kick_cooldown', delta)
		await ctx.send('New join kick pattern cooldown set: {}'.format(pretty_timedelta(delta)))

	@join.command(name='add')
	async def pattern_add(self, ctx, *, pattern: PatternConverter):
		'''Add a regex pattern to the kick pattern list.'''

		await self.db.execute(
			'INSERT INTO kick_pattern (guild_id, pattern) VALUES ($1, $2)',
			ctx.guild.id, pattern
		)

		await ctx.send('Pattern added.')

	@join.command(name='remove', aliases=['rm'])
	async def pattern_remove(self, ctx, *, pattern_id: int):
		'''Remove a pattern by id.'''

		res = await self.db.fetch(
			'DELETE FROM kick_pattern WHERE guild_id=$1 AND id=$2',
			ctx.guild.id, pattern_id
		)

		if res == 'DELETE 0':
			raise commands.CommandError('Pattern not found.')

		await ctx.send('Pattern deleted.')

	@join.command(name='enable')
	async def pattern_enable(self, ctx, *, pattern_id: int):
		'''Enable a pattern by id.'''

		res = await self.db.execute(
			'UPDATE kick_pattern SET disabled=FALSE WHERE guild_id=$1 AND id=$2',
			ctx.guild.id, pattern_id
		)

		if res == 'UPDATE 0':
			raise commands.CommandError('Pattern not found.')

		await ctx.send('Pattern enabled.')

	@join.command(name='disable')
	async def pattern_disable(self, ctx, *, pattern_id: int):
		'''Disable a pattern by id.'''

		res = await self.db.execute(
			'UPDATE kick_pattern SET disabled=TRUE WHERE guild_id=$1 AND id=$2',
			ctx.guild.id, pattern_id
		)

		if res == 'UPDATE 0':
			raise commands.CommandError('Pattern not found.')

		await ctx.send('Pattern disabled.')


def setup(bot):
	bot.add_cog(Security(bot))
