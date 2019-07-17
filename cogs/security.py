import discord
import re

from enum import Enum, IntEnum
from discord.ext import commands

from cogs.mixins import AceMixin
from cogs.ahk.ids import AHK_GUILD_ID
from utils.time import pretty_timedelta
from utils.checks import is_mod_pred
from utils.guildconfig import GuildConfig

"""

security
	overview of security settings

	enable join|mention|spam
	disable join|mention|spam

"""

SUBMODULES = ('join', 'mention', 'spam')

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

		for key, value in SecurityMode.__members__.items():
			if action == key.lower():
				return int(value)

		raise commands.CommandError(f'\'{action}\' is not a valid action.')

class SecurityMode(IntEnum):
	MUTE = 0
	KICK = 1
	BAN = 2


class ModConfig:
	_guilds = dict()

	_defaults = dict(
		mention_count=8,
		mention_per=16.0,
		spam_count=15,
		spam_per=17.0
	)

	@classmethod
	async def get_guild(cls, bot, guild_id):
		if guild_id in cls._guilds:
			return cls._guilds[guild_id]

		self = cls()

		record = await bot.db.fetchrow('SELECT * FROM mod WHERE guild_id=$1', guild_id)

		if record is None:
			await bot.db.execute('INSERT INTO mod (guild_id) VALUES ($1)', guild_id)
			record = await bot.db.fetchrow('SELECT FROM mod WHERE guild_id=$1', guild_id)

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

		for field in cls._defaults.keys():
			setattr(self, f'_{field}', record.get(field))

		self._guilds[guild_id] = self
		return self

	async def set(self, key, value):
		await self.bot.db.execute(
			f'UPDATE mod SET {key}=$1 WHERE guild_id=$2',
			value, self.guild_id
		)

		setattr(self, f'_{key}' if key in self._defaults.keys() else key, value)

	def __getattr__(self, item):
		attr = f'_{item}'
		if item in self._defaults.keys():
			if self.__dict__.get(attr, None) is not None:
				return self.__dict__[attr]
			return self._defaults[item]


class Security(AceMixin, commands.Cog):
	'''Various security features.'''

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	def _print_securitymode(self, mode):
		if mode == SecurityMode.MUTE:
			return 'MUTE'
		if mode == SecurityMode.KICK:
			return 'KICK'
		if mode == SecurityMode.BAN:
			return 'BAN'

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

		mc = await ModConfig.get_guild(self, ctx.guild.id)

		e = discord.Embed(
			description=f'VERIFICATION LEVEL: **{str(ctx.guild.verification_level).upper()}**'
		)

		e.set_author(name='Security', icon_url=self.bot.user.avatar_url)
		e.add_field(name='MENTION', value=await self._mention_status(mc))
		e.add_field(name='SPAM', value=await self._spam_status(mc))
		e.add_field(name='JOIN', value=await self._join_status(mc), inline=False)

		await ctx.send(embed=e)

	@security.command()
	async def enable(self, ctx, *, module: SubmoduleConverter):
		'''Enable a submodule.'''

		mc = await ModConfig.get_guild(self.bot, ctx.guild.id)
		await mc.set(f'{module}_enabled', True)

		await ctx.send(f'\'{module.upper()}\' enabled.')

	@security.command()
	async def disable(self, ctx, *, module: SubmoduleConverter):
		'''Disable a submodule.'''

		mc = await ModConfig.get_guild(self.bot, ctx.guild.id)
		await mc.set(f'{module}_enabled', False)

		await ctx.send(f'\'{module.upper()}\' disabled.')

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

		e = discord.Embed(description=await self._join_status(await ModConfig.get_guild(self.bot, ctx.guild.id)))

		e.add_field(name='Enabled patterns', value='\n'.join(enabled_pats) if enabled_pats else 'None')

		if disabled_pats:
			e.add_field(name='Disabled patterns', value='\n'.join(disabled_pats))

		e.set_author(name=f'JOIN', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@join.command(name='action')
	async def join_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await ModConfig.get_guild(self.bot, ctx.guild.id)
		await mc.set('join_action', action)

		await ctx.send(f'\'JOIN\' action set to \'{self._print_securitymode(action)}\'')

	async def _join_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nACTIVE PATTERNS: **{}**\nMINIMUM AGE: **{}**'.format(
			self._print_status(mc.join_enabled),
			self._print_securitymode(mc.join_action),
			await self.db.fetchval(
				'SELECT COUNT(*) FROM kick_pattern WHERE guild_id=$1 AND disabled=FALSE', mc.guild_id
			),
			'NOT SET' if mc.join_age is None else ('\n' + pretty_timedelta(mc.join_age).upper())
		)

	@join.command()
	async def add(self, ctx, *, pattern: PatternConverter):
		'''Add a regex pattern to the kick pattern list.'''

		await self.db.execute(
			'INSERT INTO kick_pattern (guild_id, pattern) VALUES ($1, $2)',
			ctx.guild.id, pattern
		)

		await ctx.send('Pattern added.')

	@join.command(aliases=['rm'])
	async def remove(self, ctx, *, pattern_id: int):
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

	@security.group(invoke_without_command=True)
	async def mention(self, ctx):
		'''Configure security settings related to mentions.'''

		mc = await ModConfig.get_guild(self.bot, ctx.guild.id)

		e = discord.Embed(description=await self._mention_status(mc))
		e.set_author(name=f'MENTION', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@mention.command(name='action')
	async def mention_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await ModConfig.get_guild(self.bot, ctx.guild.id)
		await mc.set('mention_action', action)

		await ctx.send(f'\'MENTION\' action set to \'{self._print_securitymode(action)}\'')

	async def _mention_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MENTIONS**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.mention_enabled),
			self._print_securitymode(mc.mention_action),
			mc.mention_count,
			mc.mention_per
		)

	@security.group(invoke_without_command=True)
	async def spam(self, ctx):
		'''Configure security settings related to message spam.'''

	@spam.command(name='action')
	async def spam_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await ModConfig.get_guild(self.bot, ctx.guild.id)
		await mc.set('spam_action', action)

		await ctx.send(f'\'SPAM\' action set to \'{self._print_securitymode(action)}\'')

	async def _spam_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MESSAGES**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.spam_enabled),
			self._print_securitymode(mc.spam_action),
			mc.spam_count,
			mc.spam_per
		)

	@commands.Cog.listener()
	async def on_member_join(self, member):

		gc = await GuildConfig.get_guild(member.guild.id)

		if not gc.security:
			return




	def create_cooldown(self, count, per, type=commands.BucketType.member):
		return commands.CooldownMapping.from_cooldown(count, per, type)

	@commands.Cog.listener()
	async def on_message(self, message):
		return
		if message.guild.id not in self._mentions:
			return

		for mention in message.mentions:
			if self._mentions[message.guild.id].update_rate_limit(message) is not None:
				await self.mention_handler(message)
			# TODO: also loop over role mentions??

	async def mention_handler(self, message):
		print(message)


def setup(bot):
	bot.add_cog(Security(bot))
