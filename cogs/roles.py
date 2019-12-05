import discord
import logging
import emoji

from discord.ext import commands
from asyncpg.exceptions import UniqueViolationError

from cogs.mixins import AceMixin
from utils.checks import is_mod_pred
from utils.pager import Pager
from utils.configtable import ConfigTable
from utils.string_helpers import shorten
from utils.prompter import prompter

# TODO: role add rate limiting?

log = logging.getLogger(__name__)

VALID_FIELDS = dict(
	emoji=56,
	name=199,
	description=1024
)

FIELD_TYPES = dict(
	selector=dict(
		inline=bool,
		title=str,
		description=str,
	),

)

RERUN_PROMPT = 'Re-run `roles spawn` for changes to take effect.'


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
			if emoj not in list(str(e) for e in ctx.guild.emojis):
				raise commands.CommandError('Unknown emoji.')
		return emoj


class RoleIDConverter(commands.Converter):
	async def convert(self, ctx, id):
		try:
			role = await commands.RoleConverter().convert(ctx, id)
			return role.id
		except commands.BadArgument:
			try:
				ret = int(id)
				return ret
			except ValueError:
				raise commands.CommandError('Input has to be a role or an integer.')


class TitleConverter(commands.Converter):
	async def convert(self, ctx, title):
		if len(title) > 256:
			raise commands.CommandError('Title cannot be more than 256 characters.')

		return title


class RoleTitleConverter(commands.Converter):
	async def convert(self, ctx, title):
		if len(title) > VALID_FIELDS['title']:
			raise commands.CommandError('Title cannot be more than 256 characters.')

		return title


class SelectorConverter(commands.Converter):
	async def convert(self, ctx, selector_id):
		try:
			selector_id = int(selector_id)
		except TypeError:
			raise commands.CommandError('Selector ID has to be an integer.')

		row = await ctx.bot.db.fetchrow(
			'SELECT * FROM role_selector WHERE guild_id=$1 AND id=$2',
			ctx.guild.id, selector_id
		)

		if row is None:
			raise commands.CommandError(
				'Could not find a selector with that ID. Do `roles list` to see existing selectors.'
			)

		return row


class Roles(AceMixin, commands.Cog):
	'''Create a role selection menu.'''

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(bot, table='role', primary='guild_id')
		self.bot.loop.create_task(self.setup_configs())

	# init configs
	async def setup_configs(self):
		records = await self.db.fetch('SELECT * FROM {}'.format(self.config.table))

		for record in records:
			await self.config.insert_record(record)

	async def cog_check(self, ctx):
		return await is_mod_pred(ctx)

	@commands.group(hidden=True, invoke_without_command=True)
	async def roles(self, ctx):
		await self.bot.invoke_help(ctx, 'roles')

	@roles.command()
	@commands.bot_has_permissions(embed_links=True, add_reactions=True, manage_messages=True)
	async def spawn(self, ctx):
		'''Spawn role selectors.'''

		conf = await self.config.get_entry(ctx.guild.id)

		selectors = await self.db.fetch('SELECT * FROM role_selector WHERE id=ANY($1::INTEGER[])', conf.selectors)

		if not selectors:
			raise commands.CommandError('No selectors configured. Do `roles create` to set one up.')

		if any(not selector.get('roles') for selector in selectors):
			raise commands.CommandError('You have empty selectors. Delete these or add roles to them before spawning.')

		if conf.message_ids:
			channel = ctx.guild.get_channel(conf.channel_id)
			if channel:
				for message_id in conf.message_ids:
					try:
						msg = await channel.fetch_message(message_id)
						if msg:
							await msg.delete()
					except discord.HTTPException:
						pass

		ids = list()

		for selector in selectors:
			roles = await self.db.fetch('SELECT * FROM role_entry WHERE id=ANY($1::INTEGER[])', selector.get('roles'))

			if not roles:
				continue

			e = discord.Embed(description=selector.get('description') or None)

			icon = selector.get('icon')

			e.set_author(
				name=selector.get('title') or 'Role Selector',
				icon_url=icon if icon else ctx.guild.icon_url
			)

			for role in roles:
				e.add_field(name='{} {}'.format(role.get('emoji'), role.get('name')), value=role.get('description'))

			msg = await ctx.send(embed=e)

			ids.append(msg.id)

			for role in roles:
				await msg.add_reaction(role.get('emoji'))

		await conf.update(channel_id=ctx.channel.id, message_ids=ids)

	@roles.command()
	@commands.bot_has_permissions(embed_links=True)
	async def list(self, ctx):
		'''List/print all selectors and roles.'''

		conf = await self.config.get_entry(ctx.guild.id)

		selectors = await self.db.fetch('SELECT * FROM role_selector WHERE id=ANY($1::INTEGER[])', conf.selectors)

		if not selectors:
			raise commands.CommandError('No selectors created yet. Create one using `roles create`.')

		e = discord.Embed(title='Role selectors')

		for selector in selectors:
			title = selector.get('title')

			roles = await self.db.fetch('SELECT * FROM role_entry WHERE id=ANY($1::INTEGER[])', selector.get('roles'))

			roles_list = '\n\t'.join('{0} <@{1}> (ID: {1})'.format(role.get('emoji'), role.get('role_id')) for role in roles)

			e.add_field(
				name='ID: {} {}'.format(selector.get('id'), 'No title' if title is None else shorten(title, 128)),
				value=roles_list if len(roles_list) else 'No roles.',
				inline=False
			)

		await ctx.send(embed=e)

	@roles.command()
	async def create(self, ctx, *, title: TitleConverter = None):
		'''Create a new role selector.'''

		conf = await self.config.get_entry(ctx.guild.id)

		if len(conf.selectors) == 8:
			raise commands.CommandError('Selector count of 8 reached. Aborting.')

		selector_id = await self.db.fetchval(
			'INSERT INTO role_selector (guild_id, title) VALUES ($1, $2) RETURNING id',
			ctx.guild.id, title
		)

		conf.selectors.append(selector_id)
		conf._set_dirty('selectors')

		await conf.update()

		await ctx.send('The ID of the new role selector is `{}`'.format(selector_id))

	@roles.command()
	async def delete(self, ctx, *, selector: SelectorConverter):
		'''Remove a role selector.'''

		p = prompter(
			ctx,
			title='Are you sure you want to delete this selector?',
			prompt='It contains {} role(s).'.format(len(selector.get('roles')))
		)

		if not await p:
			raise commands.CommandError('Aborted.')

		await self.db.execute('DELETE FROM role_entry WHERE id = ANY($1::INTEGER[])', selector.get('roles'))
		await self.db.execute('DELETE FROM role_selector WHERE id=$1', selector.get('id'))

		conf = await self.config.get_entry(ctx.guild.id)
		conf.selectors.remove(selector.get('id'))

		conf._set_dirty('selectors')
		await conf.update()

		await ctx.send('Selector deleted. ' + RERUN_PROMPT)

	@roles.command()
	async def add(self, ctx, selector: SelectorConverter, role: discord.Role, emoji: EmojiConverter, name: str, *, description: str):
		'''Add a role to a selector.'''

		if len(description) < 1 or len(description) > 1024:
			raise commands.CommandError('Description has to be between 1 and 1024 characters long.')

		if len(name) < 1 or len(name) > VALID_FIELDS['name']:
			raise commands.CommandError('Name has to be between 1 and 200 characters long.')

		print(selector, role, emoji, name, description)

		row_id = await self.db.fetchval(
			'INSERT INTO role_entry (role_id, emoji, name, description) VALUES ($1, $2, $3, $4) RETURNING id',
			role.id, emoji, name, description
		)

		selector.get('roles').append(row_id)

		await self.db.execute(
			'UPDATE role_selector SET roles=ARRAY_APPEND(roles, $1) WHERE id=$2',
			row_id, selector.get('id')
		)

		await ctx.send('Role \'{}\' added to selector {}. '.format(role.name, selector.get('id')) + RERUN_PROMPT)

	@roles.command()
	async def remove(self, ctx, selector: SelectorConverter, *, role: discord.Role):
		'''Remove a role from a selector.'''

		row_id = await self.db.fetchval(
			'DELETE FROM role_entry WHERE role_id=$1 AND id=ANY($2::INTEGER[]) RETURNING id',
			role.id, selector.get('roles')
		)

		if row_id is None:
			raise commands.CommandError('Role not found in specified selector.')

		await self.db.execute(
			'UPDATE role_selector SET roles=ARRAY_REMOVE(roles, $1) WHERE id=$2',
			row_id, selector.get('id')
		)

		await ctx.send('Removed role \'{}\' from selector {}.'.format(role.name, selector.get('id')))

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):

		guild_id = payload.guild_id
		channel_id = payload.channel_id
		message_id = payload.message_id
		user_id = payload.user_id
		emoji = payload.emoji

		conf = await self.config.get_entry(guild_id, construct=False)
		if conf is None:
			return

		if channel_id != conf.channel_id or message_id not in conf.message_ids:
			return

		guild = self.bot.get_guild(guild_id)
		if guild is None:
			return

		channel = guild.get_channel(channel_id)
		if channel is None:
			return

		message = await channel.fetch_message(message_id)
		if message is None:
			return

		member = guild.get_member(user_id)
		if member is None:
			return

		if member.bot:
			return

		try:
			await message.remove_reaction(emoji, member)
		except discord.HTTPException:
			pass

		selector_id = conf.selectors[conf.message_ids.index(message_id)]

		selector = await self.db.fetchrow('SELECT * FROM role_selector WHERE id=$1', selector_id)
		if selector is None:
			return

		role_row = await self.db.fetchrow(
			'SELECT * FROM role_entry WHERE emoji=$1 AND id=ANY($2::INTEGER[])',
			str(emoji), selector.get('roles')
		)

		if role_row is None:
			return

		role = guild.get_role(role_row.get('role_id'))
		if role is None:
			await channel.send(
				embed=discord.Embed(description='Could not find role with ID {}. Has it been deleted?'.format(role.id)),
				delete_after=30
			)
			return

		e = discord.Embed()
		e.set_author(name=member.display_name, icon_url=member.avatar_url)

		try:
			if role in member.roles:
				await member.remove_roles(role, reason='Removed through role selector')
				e.description = 'Removed role {}'.format(role.mention)
				await channel.send(embed=e, delete_after=10)
			else:
				await member.add_roles(role, reason='Added through role selector')
				e.description = 'Added role {}'.format(role.mention)
				await channel.send(embed=e, delete_after=10)
		except discord.HTTPException:
			e.description = 'Unable to add role {}. Does the bot have the necessary permissions?'.format(role.mention)
			await channel.send(embed=e, delete_after=30)


def setup(bot):
	bot.add_cog(Roles(bot))
