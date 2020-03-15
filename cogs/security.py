import discord
import asyncio
import re
import logging

from discord.ext import commands
from enum import IntEnum

from cogs.mixins import AceMixin
from utils.context import AceContext
from utils.configtable import ConfigTable, ConfigTableRecord


SUBMODULES = ('mention', 'spam')
SPAM_LOCK = asyncio.Lock()
MENTION_LOCK = asyncio.Lock()

log = logging.getLogger(__name__)


class SecurityConfigRecord(ConfigTableRecord):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.create_spam_cooldown()
		self.create_mention_cooldown()

	@property
	def guild(self):
		return self._config.bot.get_guild(self.guild_id)

	def create_spam_cooldown(self):
		self.spam_cooldown = commands.CooldownMapping.from_cooldown(
			self.spam_count, self.spam_per, commands.BucketType.user
		)

	def create_mention_cooldown(self):
		self.mention_cooldown = commands.CooldownMapping.from_cooldown(
			self.mention_count, self.mention_per, commands.BucketType.user
		)


class SecurityAction(IntEnum):
	MUTE = 0
	KICK = 1
	BAN = 2


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
		try:
			count = int(count)
		except ValueError:
			raise commands.CommandError('Input has to be integer.')

		if count < 3:
			raise commands.CommandError('Setting count less than 3 is not recommended.')

		return count


class PerConverter(commands.Converter):
	async def convert(self, ctx, per):
		try:
			per = float(per)
		except ValueError:
			raise commands.CommandError('Argument has to be float.')

		if per < 3.0:
			raise commands.CommandError('Setting per less than 3 is not recommended.')
		elif per > 30.0:
			raise commands.CommandError('Setting per more than 30 is not recommended.')

		return per


class Security(AceMixin, commands.Cog):
	'''Security features.

	Valid actions are: `MUTE`, `KICK` and `BAN`

	Actions are triggered when an event happens more than `COUNT` times per `PER` seconds.

	To clear a value leave all arguments blank.
	'''

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(bot, 'security', 'guild_id', record_class=SecurityConfigRecord)

	async def do_action(self, message, action, reason):
		'''Called when an event happens.'''

		member = message.author

		conf = await self.bot.config.get_entry(member.guild.id)
		ctx = await self.bot.get_context(message, cls=AceContext)

		# ignore if member is mod
		if await ctx.is_mod():
			self.bot.dispatch(
				'log', message,
				action='IGNORED {} (MEMBER IS MOD)'.format(action.name),
				reason=reason,
				severity=0
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
			self.bot.dispatch('log', message, action='{} FAILED'.format(action.name), reason=str(exc), severity=2)
			return

		# log successful security event
		self.bot.dispatch('log', message, action=action.name, reason=reason, severity=action.value)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.guild is None or message.author.bot:
			return

		mc = await self.config.get_entry(message.guild.id, construct=False)

		if mc is None:
			return

		if mc.spam_enabled:
			# with a lock, figure out if user is spamming
			async with SPAM_LOCK:
				res = mc.spam_cooldown.update_rate_limit(message)
				if res is not None:
					mc.spam_cooldown._cache[mc.spam_cooldown._bucket_key(message)].reset()

			# if so, perform the spam action
			if res is not None:
				await self.do_action(
					message, SecurityAction(mc.spam_action), reason='Member is spamming'
				)

		if mc.mention_enabled and message.mentions:

			# same here. however run once for each mention
			async with MENTION_LOCK:
				for mention in message.mentions:
					res = mc.mention_cooldown.update_rate_limit(message)
					if res is not None:
						mc.mention_cooldown._cache[mc.mention_cooldown._bucket_key(message)].reset()
						break

			if res is not None:
				await self.do_action(
					message, SecurityAction(mc.mention_action), reason='Member is mention spamming'
				)

	async def cog_check(self, ctx):
		return await ctx.is_mod()

	def _print_status(self, boolean):
		return 'ENABLED' if boolean else 'DISABLED'

	@commands.group(aliases=['sec'], invoke_without_command=True)
	async def security(self, ctx):
		'''View and edit security settings.'''

		mc = await self.config.get_entry(ctx.guild.id)

		desc = 'VERIFICATION LEVEL: **{}**'.format(str(ctx.guild.verification_level).upper())

		e = discord.Embed(description=desc)

		e.set_author(name='Security', icon_url=self.bot.user.avatar_url)
		e.add_field(name='SPAM', value=await self._spam_status(mc), inline=False)
		e.add_field(name='MENTION', value=await self._mention_status(mc), inline=False)

		await ctx.send(embed=e)

	@security.command()
	async def enable(self, ctx, *, module: SubmoduleConverter):
		'''Enable a submodule.'''

		mc = await self.config.get_entry(ctx.guild.id)

		mc.set(f'{module}_enabled', True)
		await mc.update()

		if module == 'mention':
			mc.create_mention_cooldown()
		elif module == 'spam':
			mc.create_spam_cooldown()

		await ctx.send(f'\'{module.upper()}\' enabled.')

	@security.command()
	async def disable(self, ctx, *, module: SubmoduleConverter):
		'''Disable a submodule.'''

		mc = await self.config.get_entry(ctx.guild.id)

		mc.set(f'{module}_enabled', False)
		await mc.update()

		await ctx.send(f'\'{module.upper()}\' disabled.')

	@security.group(invoke_without_command=True)
	async def spam(self, ctx):
		'''Configure security settings related to message spam.'''

		mc = await self.config.get_entry(ctx.guild.id)

		e = discord.Embed(description=await self._spam_status(mc))
		e.set_author(name=f'SPAM', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@spam.command(name='action')
	async def spam_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await self.config.get_entry(ctx.guild.id)

		await mc.update(spam_action=action.value)

		await ctx.invoke(self.spam)

	@spam.command(name='limit')
	async def spam_limit(self, ctx, count: CountConverter, per: PerConverter):
		'''Maximum mentions allowed within the time span.'''

		mc = await self.config.get_entry(ctx.guild.id)

		await mc.update(spam_count=count, spam_per=per)

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

		mc = await self.config.get_entry(ctx.guild.id)

		e = discord.Embed(description=await self._mention_status(mc))
		e.set_author(name=f'MENTION', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@mention.command(name='action')
	async def mention_action(self, ctx, action: ActionConverter):
		'''Set an action upon mention spam.'''

		mc = await self.config.get_entry(ctx.guild.id)

		await mc.update(mention_action=action.value)

		await ctx.invoke(self.mention)

	@mention.command(name='limit')
	async def mention_limit(self, ctx, count: CountConverter, per: PerConverter):
		'''Maximum mentions allowed within the time span.'''

		mc = await self.config.get_entry(ctx.guild.id)

		await mc.update(mention_count=count, mention_per=per)

		mc.create_mention_cooldown()

		await ctx.invoke(self.mention)

	async def _mention_status(self, mc):
		return 'STATUS: **{}**\nACTION: **{}**\nCOUNT: **{} MENTIONS**\nPER: **{} SECONDS**'.format(
			self._print_status(mc.mention_enabled),
			SecurityAction(mc.mention_action).name,
			mc.mention_count,
			mc.mention_per
		)


def setup(bot):
	bot.add_cog(Security(bot))
