import discord
from discord.ext import commands

from config import DEFAULT_PREFIX
from cogs.mixins import AceMixin


class PrefixConverter(commands.Converter):
	async def convert(self, ctx, prefix):
		if len(prefix) > 8 or len(prefix) < 1:
			raise commands.CommandError('Prefix must be between 1 and 8 characters.')

		if prefix != discord.utils.escape_markdown(prefix):
			raise commands.CommandError('No markdown allowed in prefix.')

		return prefix


class SettingConverter(commands.Converter):
	async def convert(self, ctx, argument):
		pass


class Configuration(AceMixin, commands.Cog):
	'''Bot configuration available to administrators and people in the moderator role.'''

	async def cog_check(self, ctx):
		return await ctx.is_mod()

	@commands.group(invoke_without_command=True)
	async def config(self, ctx):
		'''Configuration commands.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		e = discord.Embed(description='Bot configuration.')
		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

		mod_role = gc.mod_role
		mute_role = gc.mute_role
		log_channel = gc.log_channel

		format_obj = lambda o: '{}\nID: {}'.format(o.mention, o.id)

		e.add_field(name='Prefix', value='`{}`'.format(gc.prefix or DEFAULT_PREFIX))

		e.add_field(
			name='Moderation role',
			value='None' if mod_role is None else format_obj(mod_role)
		)

		e.add_field(
			name='Mute role',
			value='None' if mute_role is None else format_obj(mute_role)
		)

		e.add_field(
			name='Log channel',
			value='None' if log_channel is None else format_obj(log_channel)
		)

		e.set_footer(text='ID: {}'.format(ctx.guild.id))

		await ctx.send(embed=e)

	@config.command()
	async def prefix(self, ctx, *, prefix: PrefixConverter = None):
		'''Set a guild-specific prefix. Leave argument empty to reset to default.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		await gc.update(prefix=prefix)

		await ctx.send(
			f'Prefix set to `{prefix or DEFAULT_PREFIX}` - if you forget your prefix, '
			'simply mention the bot to open up the help menu.'
		)

	@config.command()
	@commands.has_permissions(administrator=True)  # only allow administrators to change the moderator role
	async def modrole(self, ctx, *, role: discord.Role = None):
		'''Set the moderator role. Only modifiable by server administrators. Leave argument empty to clear.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		if role is None:
			await gc.update(mod_role_id=None)
			await ctx.send('Mod role cleared.')
		else:
			await gc.update(mod_role_id=role.id)
			await ctx.send(
				f'Mod role has been set to `{role.name}` ({role.id}). '
				'Members with this role can configure and manage the bot.'
			)

	@config.command()
	@commands.has_permissions(administrator=True)  # only allow administrators to change the moderator role
	async def muterole(self, ctx, *, role: discord.Role = None):
		'''Set the muted role. Only modifiable by server administrators. Leave argument empty to clear.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		if role is None:
			await gc.update(mute_role_id=None)
			await ctx.send('Mute role cleared.')
		else:
			await gc.update(mute_role_id=role.id)
			await ctx.send(f'Mute role has been set to `{role.name}` ({role.id}).')

	@config.command()
	async def logchannel(self, ctx, *, channel: discord.TextChannel = None):
		'''Set a channel for the bot to log security-related messages.'''

		gc = await self.bot.config.get_entry(ctx.guild.id)

		if channel is None:
			await gc.update(log_channel_id=None)
			await ctx.send('Log channel cleared.')
		else:
			await gc.update(log_channel_id=channel.id)
			await ctx.send(f'Log channel has been set to `{channel.name}` ({channel.id})')


def setup(bot):
	bot.add_cog(Configuration(bot))
