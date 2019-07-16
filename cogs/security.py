import discord
import re

from discord.ext import commands

from cogs.mixins import AceMixin
from cogs.ahk.ids import AHK_GUILD_ID
from utils.checks import is_mod_pred
from utils.guildconfig import GuildConfig

"""

security
	overview of security settings

	enable join|mention|spam
	disable join|mention|spam

security join
	settings regarding new members
	
	add pattern
	remove pattern
	enable pattern
	disable pattern
	
security mention
	settings regarding mention spam
	
	action kick|mute
	
security spam
	settings regarding mass-spam

"""


class PatternConverter(commands.Converter):
	async def convert(self, ctx, pattern):
		'''Tests if the pattern is valid.'''

		try:
			re.compile(pattern)
		except re.error:
			raise commands.CommandError('Pattern is not valid RegEx.')

		return pattern


class Security(AceMixin, commands.Cog):

	_mentions = {}

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	@commands.group(aliases=['sec'], invoke_without_command=True)
	async def security(self, ctx):

		gc = await GuildConfig.get_guild(ctx.guild.id)

		pat_count = await self.db.fetchval(
			'SELECT COUNT(*) FROM kick_pattern WHERE guild_id=$1 AND disabled=FALSE',
			ctx.guild.id
		)

		e = discord.Embed()
		e.set_author(name='Security', icon_url=self.bot.user.avatar_url)

		e.add_field(name='Status', value='Enabled' if gc.security else 'Disabled')
		e.add_field(name='Kick patterns', value=f'{pat_count} active' if pat_count > 0 else 'None')

		await ctx.send(embed=e)

	@security.command()
	async def enable(self, ctx):
		'''Enable security features.'''

		if ctx.guild.id not in (AHK_GUILD_ID, 517692823621861407):
			raise commands.CommandError(
				'Currently unavailable. Contact dev directly to have security features enabled.'
			)

		gc = await GuildConfig.get_guild(ctx.guild.id)

		if gc.security:
			await ctx.send('Security already enabled.')
			return

		await gc.set('security', True)
		await ctx.send('Security enabled.')

	@security.command()
	async def disable(self, ctx):
		'''Disable security features.'''

		gc = await GuildConfig.get_guild(ctx.guild.id)

		if not gc.security:
			await ctx.send('Security not previously enabled.')
			return

		await gc.set('security', False)
		await ctx.send('Security disabled.')

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

		e.set_author(name=f'Autokicker', icon_url=self.bot.user.avatar_url)

		await ctx.send(embed=e)

	@join.command()
	async def add(self, ctx, *, pattern: PatternConverter):
		'''Add a regex pattern to the kick pattern list.'''

		await self.db.execute(
			'INSERT INTO kick_pattern (guild_id, pattern) VALUES ($1, $2)',
			ctx.guild.id, pattern
		)

		await ctx.send('Pattern added.')

	@join.command()
	async def remove(self, ctx, *, pattern_id: int):
		'''Remove a pattern by id.'''

		res = await self.db.fetch(
			'DELETE FROM kick_pattern WHERE guild_id=$1 AND pattern_id=$2',
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