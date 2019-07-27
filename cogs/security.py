import discord
import asyncio
import re

from discord.ext import commands, tasks
from enum import IntEnum
from datetime import datetime

from cogs.mixins import AceMixin
from cogs.ahk.ids import AHK_GUILD_ID
from utils.converters import TimeMultConverter, TimeDeltaConverter
from utils.time import pretty_timedelta
from utils.checks import is_mod_pred

"""

security
	overview of security settings

	enable join|mention|spam
	disable join|mention|spam

"""

ALLOWED_GUILDS = (115993023636176902, 517692823621861407)
SUBMODULES = ('join', 'mention', 'spam')
LOCK = asyncio.Lock()


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
		per = int(per)

		if per < 3:
			raise commands.CommandError('Setting count less than 3 is not recommended.')

		return per


class SecurityAction(IntEnum):
	MUTE = 0
	KICK = 1
	BAN = 2


class ModConfig:
	_guilds = dict()

	@classmethod
	async def get_guild(cls, bot, guild_id):
		if guild_id in cls._guilds:
			return cls._guilds[guild_id]

		self = cls()

		# needs a lock to prevent creating rows twice
		async with LOCK:
			record = await bot.db.fetchrow('SELECT * FROM mod WHERE guild_id=$1', guild_id)

			if record is None:
				await bot.db.execute('INSERT INTO mod (guild_id) VALUES ($1)', guild_id)
				record = await bot.db.fetchrow('SELECT * FROM mod WHERE guild_id=$1', guild_id)

		self.bot = bot
		self.id = record.get('id')
		self.guild_id = record.get('guild_id')
		self.mute_role_id = record.get('mute_role_id')

		self.join_enabled = record.get('join_enabled')
		self.mention_enabled = record.get('mention_enabled')
		self.spam_enabled = record.get('spam_enabled')

		self.join_age = record.get('join_age')

		self.join_action = record.get('join_action')
		self.mention_action = record.get('mention_action')
		self.spam_action = record.get('spam_action')

		self.spam_per = record.get('spam_per')
		self.spam_count = record.get('spam_count')

		self.mention_per = record.get('mention_per')
		self.mention_count = record.get('mention_count')

		# it's not really a model so we can store this kinda shit here IMHO
		self.create_spam_cooldown()
		self.create_mention_cooldown()

		self._guilds[guild_id] = self
		return self

	def create_spam_cooldown(self):
		self.spam_cooldown = commands.CooldownMapping.from_cooldown(
			self.spam_count, self.spam_per, commands.BucketType.user
		)

	def create_mention_cooldown(self):
		self.mention_cooldown = commands.CooldownMapping.from_cooldown(
			self.mention_count, self.mention_per, commands.BucketType.user
		)

	async def set(self, key, value):
		await self.bot.db.execute(f'UPDATE mod SET {key}=$1 WHERE guild_id=$2', value, self.guild_id)
		setattr(self, key, value)


class Security(AceMixin, commands.Cog):
	'''Security features.

	Valid actions are: `MUTE`, `KICK` and `BAN`

	Actions are triggered when an event happens more than `COUNT` times per `PER` seconds.
	'''

	def __init__(self, bot):
		super().__init__(bot)
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

		return await ModConfig.get_guild(self.bot, guild_id)

	async def _do_action(self, member, action, reason=None):
		print('{} {}'.format(action, member))

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None:
			return

		if message.author.bot:
			return

		#if await is_mod_pred(message):
		#	return

		mc = await self.get_config(message.guild.id)

		if mc.spam_enabled:
			if mc.spam_cooldown.update_rate_limit(message) is not None:
				await self._do_action(message.author, SecurityAction(mc.spam_action))

		if mc.mention_enabled:
			for mention in message.mentions:
				if mc.mention_cooldown.update_rate_limit(message) is not None:
					await self._do_action(message.author, SecurityAction(mc.mention_action))

	@commands.Cog.listener()
	async def on_member_join(self, member):
		if member.guild.id not in ModConfig._guilds:
			return

		mc = await self.get_config(member.guild.id)

		if not mc.join_enabled:
			return

		if mc.join_age is not None and member.created_at is not None:
			if mc.join_age > datetime.utcnow() - mc.created_at:
				await self._do_action(member, SecurityAction(mc.join_action))

		pats = await self.db.fetch(
			'SELECT * FROM kick_pattern WHERE guild_id=$1 AND disabled=$2',
			member.guild.id, False
		)

		print(pats)

	async def cog_check(self, ctx):
		return ctx.guild.id in ALLOWED_GUILDS and await is_mod_pred(ctx)

	def _print_status(self, boolean):
		return 'ENABLED' if boolean else 'DISABLED'

	async def _enable_feature(self, ctx, module):
		if ctx.guild.id not in (AHK_GUILD_ID, 517692823621861407):
			raise commands.CommandError(
				'Currently unavailable. Contact dev directly to have security features enabled.'
			)

	@commands.group(aliases=['sec'], invoke_without_command=True)
	async def security(self, ctx):
		'''View and edit security settings.'''

		mc = await self.get_config(ctx.guild.id)

		e = discord.Embed(
			description=f'VERIFICATION LEVEL: **{str(ctx.guild.verification_level).upper()}**'
		)

		e.set_author(name='Security', icon_url=self.bot.user.avatar_url)
		e.add_field(name='SPAM', value=await self._spam_status(mc))
		e.add_field(name='MENTION', value=await self._mention_status(mc))
		e.add_field(name='JOIN', value=await self._join_status(mc), inline=False)

		await ctx.send(embed=e)

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
		return 'STATUS: **{}**\nACTION: **{}**\nACTIVE PATTERNS: **{}**\nMINIMUM AGE: **{}**'.format(
			self._print_status(mc.join_enabled),
			SecurityAction(mc.join_action).name,
			await self.db.fetchval(
				'SELECT COUNT(*) FROM kick_pattern WHERE guild_id=$1 AND disabled=FALSE', mc.guild_id
			),
			'NOT SET' if mc.join_age is None else (pretty_timedelta(mc.join_age).upper())
		)

	@join.command(name='age')
	async def join_age(self, ctx, amount: TimeMultConverter = None, unit: TimeDeltaConverter = None):
		'''Set a minimum age for new accounts. Clear/disable by doing `security join age`.'''

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
