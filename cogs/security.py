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

	@commands.group(aliases=['sec'], invoke_without_command=False)
	async def security(self, ctx):
		'''View and edit security settings.'''

		mc = await ModConfig.get_guild(self, ctx.guild.id)

		pat_count = await self.db.fetchval(
			'SELECT COUNT(*) FROM kick_pattern WHERE guild_id=$1 AND disabled=FALSE',
			ctx.guild.id
		)

		e = discord.Embed(
			description=f'VERIFICATION LEVEL: **{str(ctx.guild.verification_level).upper()}**'
		)

		e.set_author(name='Security', icon_url=self.bot.user.avatar_url)

		mention_status = 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MESSAGES**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.mention_enabled),
			self._print_securitymode(mc.mention_action),
			mc.mention_count,
			mc.mention_per
		)

		spam_status = 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MESSAGES**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.spam_enabled),
			self._print_securitymode(mc.spam_action),
			mc.spam_count,
			mc.spam_per
		)

		join_status = 'STATUS: **{}**\nACTION: **{}**\nACTIVE PATTERNS: **{}**\nMINIMUM AGE: **{}**'.format(
			self._print_status(mc.join_enabled),
			self._print_securitymode(mc.join_action),
			pat_count,
			'NOT SET' if mc.join_age is None else ('\n' + pretty_timedelta(mc.join_age).upper())
		)

		e.add_field(
			name='MENTION',
			value=mention_status
		)

		e.add_field(
			name='SPAM',
			value=spam_status
		)

		e.add_field(
			name='JOIN',
			value=join_status,
			inline=False
		)

		await ctx.send(embed=e)

	@security.command()
	async def enable(self, ctx, module: SubmoduleConverter):
		'''Enable a submodule.'''

		print(f'self: {self}\nctx: {ctx}\nmodule: {module}')

		mc = await ModConfig.get_guild(ctx.guild.id)
		mc.set(f'{module}_enabled', True)

	@security.command()
	async def disable(self, ctx, module: SubmoduleConverter):
		'''Disable a submodule.'''

		mc = await ModConfig.get_guild(ctx.guild.id)
		mc.set(f'{module}_enabled', False)

	@security.group(invoke_without_command=True)
	async def join(self, ctx):
		'''Regex patterns that kicks new members if matching their nickname.'''

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

		e = discord.Embed()

		e.add_field(name='Enabled patterns', value='\n'.join(enabled_pats) if enabled_pats else 'None')

		if disabled_pats:
			e.add_field(name='Disabled patterns', value='\n'.join(disabled_pats))

		e.set_author(name=f'Join Settings', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

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

	@join.command()
	async def enable(self, ctx, *, pattern_id: int):
		'''Enable a pattern by id.'''

		res = await self.db.execute(
			'UPDATE kick_pattern SET disabled=FALSE WHERE guild_id=$1 AND id=$2',
			ctx.guild.id, pattern_id
		)

		if res == 'UPDATE 0':
			raise commands.CommandError('Pattern not found.')

		await ctx.send('Pattern enabled.')

	@join.command()
	async def disable(self, ctx, *, pattern_id: int):
		'''Disable a pattern by id.'''

		res = await self.db.execute(
			'UPDATE kick_pattern SET disabled=TRUE WHERE guild_id=$1 AND id=$2',
			ctx.guild.id, pattern_id
		)

		if res == 'UPDATE 0':
			raise commands.CommandError('Pattern not found.')

		await ctx.send('Pattern disabled.')


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
