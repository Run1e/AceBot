import discord
import logging

from discord.ext import commands


from cogs.mixins import AceMixin
from utils.checks import is_mod_pred
from utils.string_helpers import craft_welcome


class Welcome(AceMixin, commands.Cog):
	'''Show welcome messages to new members.

	Welcome message replacements:
	`{user}` - member mention
	`{guild}` - server name
	`{member_count}` - server member count
	'''

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	async def get_welcome(self, guild_id, construct=True):
		row = await self.db.fetchrow('SELECT * FROM welcome WHERE guild_id=$1', guild_id)

		if row or not construct:
			return row

		await self.db.execute('INSERT INTO welcome (guild_id) VALUES ($1)', guild_id)
		return await self.db.fetchrow('SELECT * FROM welcome WHERE guild_id=$1', guild_id)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		row = await self.get_welcome(member.guild.id, construct=False)

		if row is None or row.get('enabled') is False or row.get('content') is None or row.get('channel_id') is None:
			return

		channel = member.guild.get_channel(row.get('channel_id'))

		if channel is not None:
			await channel.send(craft_welcome(member, row.get('content')))

	@commands.group(hidden=True)
	async def welcome(self, ctx):
		pass

	@welcome.command(aliases=['msg'])
	async def message(self, ctx, *, message: str):
		'''Set a new welcome message.'''

		if len(message) > 1024:
			raise commands.CommandError('Welcome message has to be shorter than 1024 characters.')

		# make sure an entry for this exists...
		row = await self.get_welcome(ctx.guild.id)

		await self.db.execute(
			'UPDATE welcome SET content=$2 WHERE id=$1',
			row.get('id'), message
		)

		await ctx.send('Welcome message updated. Do `welcome test` to test.')

	@welcome.command()
	async def channel(self, ctx, *, channel: discord.TextChannel = None):
		'''Set or view welcome message channel.'''

		row = await self.get_welcome(ctx.guild.id)

		if channel is None:
			if row.get('channel_id') is None:
				raise commands.CommandError('Welcome channel not yet set.')

			channel = ctx.guild.get_channel(row.get('channel_id'))
			if channel is None:
				raise commands.CommandError('Channel previously set but not found, try setting a new one.')

		else:
			await self.db.execute(
				'UPDATE welcome SET channel_id=$2 WHERE id=$1',
				row.get('id'), channel.id
			)

		await ctx.send(f'Welcome channel set to {channel.mention}')

	@welcome.command()
	async def test(self, ctx):
		'''Test your welcome command.'''

		row = await self.get_welcome(ctx.guild.id)

		if row.get('channel_id') is not None:
			channel = ctx.guild.get_channel(row.get('channel_id'))
		else:
			channel = False

		if row.get('enabled') is False:
			await ctx.send('Welcome message are disabled. Enable with `welcome enable`.')
		elif row.get('content') is None:
			await ctx.send('No welcome message set. Set with `welcome message <message>`')
		elif channel is None:
			await ctx.send('Welcome channel set but not found. Set a new one with `welcome channel <channel>`')
		elif channel is False:
			await ctx.send('No welcome channel set. Set with `welcome channel <channel>`')
		else:
			await self.on_member_join(ctx.author)

	@welcome.command()
	async def enable(self, ctx):
		'''Enable welcome messages.'''

		row = await self.get_welcome(ctx.guild.id)

		if row.get('enabled') is True:
			raise commands.CommandError('Welcome messages already enabled.')

		await self.db.execute('UPDATE welcome SET enabled=$2 WHERE id=$1', row.get('id'), True)
		await ctx.send('Welcome messages enabled.')

	@welcome.command()
	async def disable(self, ctx):
		'''Disable welcome messages.'''

		row = await self.get_welcome(ctx.guild.id)

		if row.get('enabled') is False:
			raise commands.CommandError('Welcome messages already disabled.')

		await self.db.execute('UPDATE welcome SET enabled=$2 WHERE id=$1', row.get('id'), False)
		await ctx.send('Welcome messages disabled.')


def setup(bot):
	bot.add_cog(Welcome(bot))
