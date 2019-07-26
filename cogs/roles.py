import discord
import logging
import emoji

from discord.ext import commands
from asyncpg.exceptions import UniqueViolationError

from cogs.mixins import AceMixin
from utils.checks import is_mod_pred
from utils.pager import Pager

# TODO: role add rate limiting?


class RolePager(Pager):
	async def craft_page(self, e, page, entries):
		for role in entries:
			e.add_field(
				name=role.name,
				value='ID: {}'.format(str(role.id))
			)

		e.set_author(
			name=self.ctx.guild.name,
			icon_url=self.ctx.guild.icon_url
		)


class EmojiConverter(commands.Converter):
	async def convert(self, ctx, emoj):
		if emoj not in emoji.UNICODE_EMOJI:
			raise commands.CommandError('Unknown emoji.')
		return emoj


class RoleIDConverter(commands.Converter):
	async def convert(self, ctx, id):
		try:
			role = await commands.RoleConverter().convert(ctx, id)
			return role.id
		except TypeError:
			try:
				ret = int(id)
				return ret
			except ValueError:
				raise commands.CommandError('Input has to be a role or an integer.')


class Roles(AceMixin, commands.Cog):
	'''Create a role selection menu.'''

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	async def get_config(self, guild_id):
		conf = await self.db.fetchrow('SELECT * FROM role WHERE guild_id=$1', guild_id)
		if conf is not None:
			return conf

		await self.db.execute('INSERT INTO role (guild_id) VALUES ($1)', guild_id)
		return await self.db.fetchrow('SELECT * FROM role WHERE guild_id=$1', guild_id)

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):

		stored_msg_id = await self.db.fetchval('SELECT message_id FROM role WHERE guild_id=$1', payload.guild_id)
		if stored_msg_id != payload.message_id:
			return

		guild = self.bot.get_guild(payload.guild_id)
		if guild is None:
			return

		member = guild.get_member(payload.user_id)
		if member is None or member.bot:
			return

		channel = guild.get_channel(payload.channel_id)
		if channel is None:
			return

		message = await channel.fetch_message(payload.message_id)
		if message is None:
			return

		await message.remove_reaction(payload.emoji, member)

		conf = await self.get_config(payload.guild_id)

		role_row = await self.db.fetchrow(
			'SELECT * FROM role_entry WHERE emoji=$1 AND id = ANY($2::INTEGER[])',
			str(payload.emoji), conf.get('roles')
		)

		if role_row is None:
			return

		role = guild.get_role(role_row.get('role_id'))
		if role is None:
			await channel.send(
				f'Role with ID `{role_row.get("role_id")}` registered but not found. Has it been deleted?',
				delete_after=10
			)
			return

		if role in member.roles:
			await member.remove_roles(role, reason='Removed through Role Selector')
			added = False
		else:
			await member.add_roles(role, reason='Added through Role Selector')
			added = True

		e = discord.Embed(
			title='Role {}'.format('Added' if added else 'Removed'),
			description=role.mention
		)

		e.set_author(name=member.display_name, icon_url=member.avatar_url)

		await channel.send(embed=e, delete_after=10)

	@commands.group(hidden=True)
	async def roles(self, ctx):
		pass

	@roles.command()
	async def spawn(self, ctx):
		'''Spawns the role selector. Deletes previous role selector instance.'''

		conf = await self.get_config(ctx.guild.id)
		if not len(conf.get('roles')):
			raise commands.CommandError('No roles configured.')

		e = discord.Embed(
			description='Click the reactions to give or remove roles.'
		)

		e.set_author(
			name='{} Roles'.format(ctx.guild.name),
			icon_url=ctx.guild.icon_url
		)

		guild_roles = await self.db.fetch('SELECT * FROM role_entry WHERE id = ANY($1::INTEGER[])', conf.get('roles'))

		# this thing could probably be improved
		for role_entry_id in conf.get('roles'):
			for role in guild_roles:
				if role_entry_id == role.get('id'):
					e.add_field(
						name='{} {}'.format(role.get('emoji'), role.get('name')),
						value=role.get('description')
					)

		# delete old message
		if conf.get('message_id') is not None:
			old_channel = ctx.guild.get_channel(conf.get('channel_id'))
			if old_channel is not None:
				try:
					old_message = await old_channel.fetch_message(conf.get('message_id'))
					await old_message.delete()
				except discord.HTTPException:
					pass

		try:
			await ctx.message.delete()
		except discord.HTTPException:
			pass

		msg = await ctx.send(embed=e)

		for role_entry_id in conf.get('roles'):
			for role in guild_roles:
				if role_entry_id == role.get('id'):
					await msg.add_reaction(role.get('emoji'))

		await self.db.execute(
			'UPDATE role SET channel_id=$2, message_id=$3 WHERE id=$1',
			conf.get('id'), msg.channel.id, msg.id
		)

	@roles.command()
	async def add(self, ctx, role: discord.Role, emoji: EmojiConverter, name: str, *, description: str):
		'''Add a new role to the role selector. To add non-mentionable roles, get their ID using `roles all`.'''

		if len(description) < 1 or len(description) > 1024:
			raise commands.CommandError('Description has to be between 1 and 1024 characters long.')

		if len(name) < 1 or len(name) > 248:
			raise commands.CommandError('Name has to be between 1 and 250 characters long.')

		try:
			id = await self.db.fetchval(
				'INSERT INTO role_entry (role_id, emoji, name, description) VALUES ($1, $2, $3, $4) RETURNING id',
				role.id, str(emoji), name, description
			)
		except UniqueViolationError:
			raise commands.CommandError('Role already added.')

		conf = await self.get_config(ctx.guild.id)

		await self.db.execute('UPDATE role SET roles = roles || $1 WHERE id=$2', (id,), conf.get('id'))

		await ctx.send('Role added. Do `roles spawn` to create new role selector menu.')

	@roles.command()
	async def remove(self, ctx, role: RoleIDConverter):
		'''Remove a role from the role selector.'''

		conf = await self.get_config(ctx.guild.id)

		role_row = await self.db.fetchrow(
			'SELECT * FROM role_entry WHERE role_id=$1 AND id = ANY($2::INTEGER[])',
			role, conf.get('roles')
		)

		if role_row is None:
			raise commands.CommandError('Role not in the role selector.')

		await self.db.execute('DELETE FROM role_entry WHERE id=$1', role_row.get('id'))
		await self.db.execute('UPDATE role SET roles = array_remove(roles, $1)', role_row.get('id'))

		await ctx.send('Role removed from the role selector.')

	@roles.command()
	async def moveup(self, ctx, role: RoleIDConverter):
		'''Move a role up in the Role Selector.'''

		await self._moverole(ctx, role, -1)
		await ctx.send('Role moved up.')

	@roles.command()
	async def movedown(self, ctx, role: RoleIDConverter):
		'''Move a role down in the Role Selector'''

		await self._moverole(ctx, role, 1)
		await ctx.send('Role moved down.')

	async def _moverole(self, ctx, role, direction):
		conf = await self.get_config(ctx.guild.id)

		role_row = await self.db.fetchrow(
			'SELECT * FROM role_entry WHERE role_id=$1 AND id = ANY($2::INTEGER[])',
			role, conf.get('roles')
		)

		if role_row is None:
			raise commands.CommandError('Role not registered.')

		ids = conf.get('roles')

		if len(ids) == 1:
			raise commands.CommandError('Role is the only role registered.')

		pos = None

		for idx, id in enumerate(ids):
			if id == role_row.get('id'):
				pos = idx
				break

		if pos is None:
			raise commands.CommandError('Role not registered.')

		if pos == 0 and direction == -1:
			raise commands.CommandError('Role is already first.')

		if pos == len(ids) - 1 and direction == 1:
			raise commands.CommandError('Role is already last.')

		# actually do the swap
		ids[pos], ids[pos + direction] = ids[pos + direction], ids[pos]
		await self.db.execute('UPDATE role SET roles=$1 WHERE id=$2', ids, conf.get('id'))

	@roles.command()
	async def print(self, ctx):
		'''Print information about the roles currently in the Role Selector.'''

		conf = await self.get_config(ctx.guild.id)

		role_rows = await self.db.fetch(
			'SELECT * FROM role_entry WHERE id = ANY($1::INTEGER[])',
			conf.get('roles')
		)

		if not role_rows:
			raise commands.CommandError('No roles registered or found.')

		e = discord.Embed()

		for role in role_rows:
			e.add_field(
				name=role.get('name'),
				value='ID: {}\nROLE ID: {}\nEMOJI: {}'.format(role.get('id'), role.get('role_id'), role.get('emoji'))
			)

		await ctx.send(embed=e)

	@roles.command(name='list', aliases=['all'])
	async def _list(self, ctx):
		'''List all roles in this server.'''

		p = RolePager(ctx, list(reversed(ctx.guild.roles[1:])), per_page=25)
		await p.go()


def setup(bot):
	bot.add_cog(Roles(bot))
