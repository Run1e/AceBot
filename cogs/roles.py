import discord
import logging
import emoji
import asyncio

from discord.ext import commands
from asyncpg.exceptions import UniqueViolationError
from collections import namedtuple

from cogs.mixins import AceMixin
from utils.checks import is_mod_pred
from utils.pager import Pager
from utils.configtable import ConfigTable
from utils.string_helpers import shorten
from utils.prompter import prompter

# TODO: role add rate limiting?
# TODO: don't allow the @everyone role
# TODO: ignore command input when being prompted
# TODO: transfer roles between selectors

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

UP_EMOJI = '🔼'
DOWN_EMOJI = '🔽'
MOVEUP_EMOJI = '⏫'
MOVEDOWN_EMOJI = '⏬'
ADD_ROLE_EMOJI = '🇷'
ADD_SEL_EMOJI = '🇸'
DEL_EMOJI = '➖'
STOP_EMOJI = '✏️'

EMBED_EMOJIS = (
	UP_EMOJI, DOWN_EMOJI, MOVEUP_EMOJI, MOVEDOWN_EMOJI,
	ADD_SEL_EMOJI, ADD_ROLE_EMOJI, DEL_EMOJI, STOP_EMOJI
)


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
	async def convert(self, ctx, arg):
		try:
			role = await commands.RoleConverter().convert(ctx, arg)
			_id = role.id
		except commands.BadArgument:
			try:
				ret = int(arg)
				_id = ret
			except ValueError:
				raise commands.CommandError('Input has to be a role or an integer.')

		if await ctx.bot.db.fetchval('SELECT id FROM role_entry WHERE guild_id=$1 AND role_id=$2', ctx.guild.id, _id):
			raise commands.CommandError('This role already exists in a selector somewhere.')

		return _id


class RoleTitleConverter(commands.Converter):
	async def convert(self, ctx, title):
		if len(title) > 199:
			raise commands.CommandError('Role field titles cannot be more than 199 characters.')

		return title


class RoleDescConverter(commands.Converter):
	async def convert(self, ctx, title):
		if len(title) > 1024:
			raise commands.CommandError('Role field descriptions cannot be more than 1024 characters.')

		return title


class SelectorTitleConverter(commands.Converter):
	async def convert(self, ctx, title):
		if len(title) > 256:
			raise commands.CommandError('Role selector titles cannot be more than 256 characters.')

		return title


class SelectorDescConverter(commands.Converter):
	async def convert(self, ctx, title):
		if len(title) > 1024:
			raise commands.CommandError('Role selector descriptions cannot be more than 1024 characters.')

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


NEW_ROLE_PREDS = (
	('What role do you want to add? (Send a role mention or just the role ID)', RoleIDConverter),
	('What name should this role entry have?', RoleTitleConverter),
	('What emoji should be associated with this role?', EmojiConverter),
	('What description should this role have?', RoleDescConverter)
)

NEW_SEL_PREDS = (
	('What should the name of the selector be?', SelectorTitleConverter),
	('What should the description of this selector be?', SelectorDescConverter)
)


class MaybeDirty:
	dirty = False

	def set_dirty(self):
		self.dirty = True

	def set_clean(self):
		self.dirty = False


class MaybeNew:
	@property
	def is_new(self):
		return self.id is None


class Role(MaybeDirty, MaybeNew):
	def __init__(self, _id, role_id, name, emoji, desc):
		self.id = _id
		self.role_id = role_id
		self.name = name
		self.emoji = emoji
		self.desc = desc


class Selector(MaybeDirty, MaybeNew):
	def __init__(self, _id, title, desc, roles: list):
		self.id = _id
		self.title = title
		self.desc = desc
		self.roles = roles

	def add_role(self, index, role):
		self.set_dirty()
		self.roles.insert(index, role)

	@property
	def role_ids(self):
		return list(role.id for role in self.roles if role.id is not None)


class RoleHead(MaybeDirty):
	front = '-> '
	back = ' <-'

	def __init__(self, conf, selectors: list):
		self.conf = conf
		self.selectors = selectors

		self.selector_pos = 0
		self.role_pos = None

	@property
	def selected(self):
		if self.role_pos is None:
			return self.selector
		else:
			return self.selector.roles[self.role_pos]

	@property
	def selector(self):
		return self.selectors[self.selector_pos]

	@property
	def role(self):
		if self.role_pos is None:
			return None

		return self.selector.roles[self.role_pos]

	@property
	def selector_max(self):
		return len(self.selectors) - 1

	@property
	def role_max(self):
		return len(self.selector.roles) - 1

	def add_selector(self, index, selector):
		self.set_dirty()
		self.selectors.insert(index, selector)

	def move_selector(self, direction):
		self.set_dirty()

		swap_with = (self.selector_pos + direction) % (self.selector_max + 1)
		self.selectors[self.selector_pos], self.selectors[swap_with] = self.selectors[swap_with], self.selectors[self.selector_pos]

		self.selector_pos = swap_with

	def move_role(self, direction):
		sel = self.selector
		sel.set_dirty()

		new_sel_pos = (self.selector_pos + direction) % (self.selector_max + 1)
		new_sel = self.selectors[new_sel_pos]

		# if this is the last role in this selector and we're moving down
		if direction == 1 and self.role_pos == self.role_max:
			# move the role to the first role slot in the selector below
			new_sel.add_role(0, sel.roles.pop(self.role_pos))
			self.selector_pos = new_sel_pos
			self.role_pos = 0

		# if this is the first role in this selector and we're moving up
		elif direction == -1 and self.role_pos == 0:
			# move the role to the last role slot in the selector above
			new_role_pos = len(new_sel.roles)
			new_sel.add_role(new_role_pos, sel.roles.pop(self.role_pos))
			self.selector_pos = new_sel_pos
			self.role_pos = new_role_pos - 1

		# otherwise, just swap the two roles in this selector
		else:
			swap_with = (self.role_pos + direction) % len(sel.roles)
			sel.roles[self.role_pos], sel.roles[swap_with] = sel.roles[swap_with], sel.roles[self.role_pos]
			self.role_pos = swap_with

	def up(self):
		if self.role_pos is None:
			# get the above selector
			self.selector_pos = (self.selector_pos - 1) % (self.selector_max + 1)

			role_count = len(self.selector.roles)

			# if it has items, select the last item in that selector
			if role_count:
				self.role_pos = role_count - 1
			else:
				self.role_pos = None

		# in a selector
		else:
			if self.role_pos > 0:
				self.role_pos -= 1
			else:
				self.role_pos = None

	def down(self):
		# selector is currently selected
		if self.role_pos is None:
			# check if there's a role in the selector we can select
			if len(self.selector.roles) > 0:
				self.role_pos = 0
			else:
				# otherwise go to the selector below
				self.selector_pos = (self.selector_pos + 1) % (self.selector_max + 1)

		# role is currently selected
		else:
			# if there's a role below to select...
			if self.role_pos != self.role_max:
				self.role_pos += 1

			# otherwise, select next selector
			else:
				self.role_pos = None
				self.selector_pos = (self.selector_pos + 1) % (self.selector_max + 1)

	def embed(self, footer=''):
		self.updated = False

		e = discord.Embed()

		if not self.selectors:
			e.description = 'Click {} to create your first role selector!'.format(ADD_SEL_EMOJI)
			return e

		e.set_footer(text=footer)

		def wrap(to_wrap):
			return self.front + to_wrap + self.back

		for sel_idx, selector in enumerate(self.selectors):
			rls = list()

			for role_idx, (role) in enumerate(selector.roles):
				string = '{} {}'.format(role.emoji, shorten(role.name, 64))
				rls.append(wrap(string) if sel_idx == self.selector_pos and role_idx == self.role_pos else string)

			e.add_field(
				name=wrap(selector.title) if self.role_pos is None and sel_idx == self.selector_pos else selector.title,
				value='\n'.join(rls) if rls else 'Select the selector and press {} to add a role!'.format(ADD_ROLE_EMOJI),
				inline=False
			)

		return e


class Roles(AceMixin, commands.Cog):
	'''Create role selection menu(s).'''

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
	async def edit(self, ctx):
		'''Reorder selectors or roles.'''

		conf = await self.config.get_entry(ctx.guild.id)

		slcs = await self.db.fetch(
			'''
			SELECT rs.*
			FROM role_selector as rs
			JOIN unnest($1::INTEGER[]) WITH ORDINALITY t(id, ord) USING (id)
			WHERE id=ANY($1::INTEGER[])
			ORDER BY t.ord
			''',
			conf.selectors
		)

		selectors = list()

		for slc in slcs:

			roles = await self.db.fetch(
				'''
				SELECT re.* 
				FROM role_entry as re 
				JOIN unnest($1::INTEGER[]) WITH ORDINALITY t(id, ord) USING (id) 
				WHERE id=ANY($1::INTEGER[])
				ORDER BY t.ord
				''',
				slc.get('roles')
			)

			selector = Selector(
				slc.get('id'),
				slc.get('title'),
				slc.get('description'),
				list(
					Role(r.get('id'), r.get('role_id'), r.get('name'), r.get('emoji'), r.get('description'))
					for r in roles
				)
			)

			selectors.append(selector)

		head = RoleHead(conf, selectors)

		msg = await ctx.send(embed=head.embed())

		for emoji in EMBED_EMOJIS:
			await msg.add_reaction(emoji)

		def pred(reaction, user):
			return reaction.message.id == msg.id and user != self.bot.user

		async def close():
			try:
				await msg.delete()
				await ctx.send('Use `roles spawn` to see new selector(s).')
			except discord.HTTPException:
				pass

		while True:
			#if head.updated:
			await msg.edit(embed=head.embed())

			try:
				reaction, user = await self.bot.wait_for('reaction_add', check=pred, timeout=60.0)
			except asyncio.TimeoutError:
				await close()
				break
			else:
				await msg.remove_reaction(reaction.emoji, user)

				reac = str(reaction)
				print(reac)

				if reac == ADD_SEL_EMOJI:
					selector_data = await self._multiprompt(ctx, msg, NEW_SEL_PREDS)
					if selector_data is None:
						continue

					selector = Selector(None, *selector_data, list())
					selector.set_dirty()

					head.add_selector(head.selector_pos + 1, selector)

				elif reac == ADD_ROLE_EMOJI:
					role_data = await self._multiprompt(ctx, msg, NEW_ROLE_PREDS)
					if role_data is None:
						continue

					role = Role(None, *role_data)
					head.selector.add_role(0 if head.role_pos is None else head.role_pos + 1, role)

				# rest of the actions assume at least one item (selector) is present
				if not head.selectors:
					continue

				if reac == DOWN_EMOJI:
					head.down()
				if reac == UP_EMOJI:
					head.up()

				if reac in (MOVEUP_EMOJI, MOVEDOWN_EMOJI):
					direction = 1 if reac == MOVEUP_EMOJI else -1

					if head.role_pos is None:
						head.move_selector(direction)
					else:
						head.move_role(direction)


	async def _multiprompt(self, ctx, msg, preds):
		retry = 'Please try again!'
		outs = list()

		def pred(message):
			return message.author.id == ctx.author.id and ctx.channel.id == ctx.channel.id

		def new_embed(question):
			e = discord.Embed(description=question)
			e.set_footer(text='Send a message below with your answer!')
			return e

		for question, test in preds:
			await msg.edit(embed=new_embed(question))

			while True:
				try:
					message = await self.bot.wait_for('message', check=pred, timeout=60.0)
					await message.delete()
				except asyncio.TimeoutError:
					return None

				try:
					value = await test().convert(ctx, message.content)
				except commands.CommandError as exc:
					e = msg.embeds[0]
					e.set_footer(text='NOTE: ' + str(exc) + ' ' + retry)
					await msg.edit(embed=e)
					continue

				outs.append(value)
				break

		return outs

	@roles.command()
	@commands.bot_has_permissions(embed_links=True, add_reactions=True, manage_messages=True)
	async def spawn(self, ctx):
		'''Spawn role selectors.'''

		conf = await self.config.get_entry(ctx.guild.id)

		selectors = await self.db.fetch(
			'''SELECT rs.*
			FROM role_selector as rs
			JOIN unnest($1::INTEGER[]) WITH ORDINALITY t(id, ord) USING (id)
			WHERE id=ANY($1::INTEGER[])
			ORDER BY t.ord
			''',
			conf.selectors)

		if not selectors:
			raise commands.CommandError('No selectors configured. Do `roles edit` to set one up.')

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

			# https://stackoverflow.com/questions/866465/order-by-the-in-value-list
			roles = await self.db.fetch(
				'''
				SELECT re.* 
				FROM role_entry as re 
				JOIN unnest($1::INTEGER[]) WITH ORDINALITY t(id, ord) USING (id) 
				WHERE id=ANY($1::INTEGER[])
				ORDER BY t.ord
				''',
				selector.get('roles')
			)

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


"""
	async def _add_selector(self, conf, title, description=None, roles=None, pos=None):
		if len(conf.selectors) == 8:
			raise commands.CommandError('Selector count of 8 reached. Aborting.')

		selector_id = await self.db.fetchval(
			'INSERT INTO role_selector (guild_id, title, description, roles) VALUES ($1, $2, $3, $4) RETURNING id',
			conf.guild_id, title, description, roles
		)

		if pos is None:
			conf.selectors.append(selector_id)
		else:
			conf.selectors.insert(pos, selector_id)

		conf._set_dirty('selectors')

		await conf.update()

		return selector_id

	async def _rm_selector(self, conf, selector_id):
		selector = await self.db.fetchrow('SELECT * FROM role_selector WHERE id=$1', selector_id)
		if selector is None:
			raise commands.CommandError('Failed to find selector.')

		await self.db.execute('DELETE FROM role_entry WHERE id=ANY($1::INTEGER[])', selector.get('roles'))
		await self.db.execute('DELETE FROM role_selector WHERE id=$1', selector_id)

		conf.selectors.remove(selector_id)
		conf._set_dirty('selectors')

		await conf.update()

	async def _add_role(self, guild_id, role_id, name, emoji, description):
		row_id = await self.db.fetchval(
			'INSERT INTO role_entry (guild_id, role_id, name, emoji, description) VALUES ($1, $2, $3, $4, $5) RETURNING id',
			guild_id, role_id, name, emoji, description
		)

		return row_id

	async def _multiprompt(self, ctx, msg, questions, tests):
		retry = 'Please try again!'
		outs = list()

		def pred(message):
			return message.author.id == ctx.author.id and ctx.channel.id == ctx.channel.id

		def new_embed(question):
			e = discord.Embed(description=question)
			e.set_footer(text='Send a message below with your answer!')
			return e

		for question, test in zip(questions, tests):
			await msg.edit(embed=new_embed(question))

			while True:
				try:
					message = await self.bot.wait_for('message', check=pred, timeout=60.0)
					await message.delete()
				except asyncio.TimeoutError:
					return None

				try:
					value = await test().convert(ctx, message.content)
				except commands.CommandError as exc:
					e = msg.embeds[0]
					e.set_footer(text='NOTE: ' + str(exc) + ' ' + retry)
					await msg.edit(embed=e)
					continue

				outs.append(value)
				break

		return outs

	async def _reorder_selector(self, selector_id, roles):
		await self.db.execute(
			'UPDATE role_selector SET roles=$1 WHERE id=$2',
			[role['id'] for role in roles], selector_id
		)

	@roles.command()
	async def edit(self, ctx):
		'''Reorder selectors or roles.'''

		conf = await self.config.get_entry(ctx.guild.id)

		selectors = await self.db.fetch(
			'''SELECT rs.*
			FROM role_selector as rs
			JOIN unnest($1::INTEGER[]) WITH ORDINALITY t(id, ord) USING (id)
			WHERE id=ANY($1::INTEGER[])
			ORDER BY t.ord
			''',
			conf.selectors
		)

		pointer = [0, None]
		data = list()

		for slc in selectors:

			roles = await self.db.fetch(
				'''
				SELECT re.* 
				FROM role_entry as re 
				JOIN unnest($1::INTEGER[]) WITH ORDINALITY t(id, ord) USING (id) 
				WHERE id=ANY($1::INTEGER[])
				ORDER BY t.ord
				''',
				slc.get('roles')
			)

			val = dict(
				id=slc.get('id'),
				title=slc.get('title'),
				roles=[dict(id=r.get('id'), emoji=r.get('emoji'), name=r.get('name')) for r in roles]
			)

			data.append(val)

		msg = await ctx.send(embed=self._craft_embed(data, pointer))

		for emoji in (UP_EMOJI, DOWN_EMOJI, MOVEUP_EMOJI, MOVEDOWN_EMOJI, ADD_EMOJI, DEL_EMOJI, STOP_EMOJI):
			await msg.add_reaction(emoji)

		def pred(reaction, user):
			return reaction.message.id == msg.id and user != self.bot.user

		async def close():
			try:
				await msg.delete()
				await ctx.send('Use `roles spawn` to see new selector(s).')
			except discord.HTTPException:
				pass

		while True:
			await msg.edit(embed=self._craft_embed(data, pointer))

			try:
				reaction, user = await self.bot.wait_for('reaction_add', check=pred, timeout=60.0)
			except asyncio.TimeoutError:
				await close()
				break
			else:
				await msg.remove_reaction(reaction.emoji, user)

				str_reac = str(reaction)

				if str_reac == ADD_EMOJI:
					# new selector
					if pointer[1] is None:
						role_data = await self._multiprompt(ctx, msg, NEWSEL_VARS, NEWSEL_TESTS)
						if role_data is None:
							return

						sel_name, role_id, role_name, role_emoji, role_desc = role_data

						try:
							role_row_id = await self._add_role(
								ctx.guild.id,
								role_id,
								role_name,
								role_emoji,
								role_desc
							)
						except UniqueViolationError:
							await ctx.send('This role already exists in some other selector.', delete_after=6)
							continue

						selector_id = await self._add_selector(
							conf,
							title=sel_name,
							roles=[role_row_id],
							pos=pointer[0]
						)

						sel_role_data = dict(id=role_row_id, emoji=role_emoji, name=role_name)
						new_pos = 0 if not data else pointer[0] + 1

						data.insert(
							new_pos,
							dict(id=selector_id, title=sel_name, roles=[sel_role_data])
						)

						pointer[0] = new_pos
						pointer[1] = None

					# new role
					else:
						role_data = await self._multiprompt(ctx, msg, ROLE_VARS, ROLE_TESTS)
						if role_data is None:
							continue

						role_id, role_name, role_emoji, role_desc = role_data

						try:
							role_row_id = await self._add_role(
								ctx.guild.id,
								role_id,
								role_name,
								role_emoji,
								role_desc
							)
						except UniqueViolationError:
							await ctx.send('This role already exists in some other selector.', delete_after=6)
							continue

						data[pointer[0]]['roles'].insert(
							pointer[1] + 1,
							dict(id=role_row_id, emoji=role_emoji, name=role_name)
						)

						await self._reorder_selector(data[pointer[0]]['id'], data[pointer[0]]['roles'])

						pointer[1] += 1


				if str_reac == STOP_EMOJI:
					try:
						await close()
					except discord.HTTPException:
						pass

					break

				if not data:
					continue

				# assume some data exists if reached here

				if str_reac == DEL_EMOJI:
					if pointer[1] is None:
						p = prompter(
							ctx,
							'Delete selector?',
							'This selector has {} role(s).'.format(len(data[pointer[0]]['roles']))
						)

						if not await p:
							continue

						# remove current selector
						selector_id = data[pointer[0]]['id']
						await self._rm_selector(conf, selector_id)
						data.pop(pointer[0])
					else:
						# delete current role
						selector_id = data[pointer[0]]['id']

						# if this is the only role in the selector, remove the whole selector
						if len(data[pointer[0]]['roles']) == 1:
							await self._rm_selector(conf, selector_id)
							data.pop(pointer[0])

						# remove only one role
						else:
							role = data[pointer[0]]['roles'].pop(pointer[1])

							# delete role
							await self.db.execute('DELETE FROM role_entry WHERE id=$1', role['id'])
							await self._reorder_selector(data[pointer[0]]['id'], data[pointer[0]]['roles'])

					# clamp pointer if we deleted anything
					if not data:
						# reset if "empty"
						pointer[0] = 0
						pointer[1] = None
					else:
						# otherwise, jump to closest selector or role
						sl = len(data) - 1

						# jump to last selector if beyond last selector
						if pointer[0] > sl:
							pointer[0] = sl
							pointer[1] = None

						# if current selector is valid, jump to the closest role
						elif pointer[1] is not None:
							rl = len(data[pointer[0]]['roles'])
							pointer[1] = min(max(pointer[1], rl - 1), 0)

				if str_reac in (UP_EMOJI, DOWN_EMOJI):
					_dir = -1 if str_reac == UP_EMOJI else 1
					self._move(data, pointer, _dir)

				if str_reac in (MOVEUP_EMOJI, MOVEDOWN_EMOJI):
					_dir = -1 if str_reac == MOVEUP_EMOJI else 1

					# move selectors
					if pointer[1] is None:
						selector_pos = pointer[0]

						# nothing to reorder if less than two selectors
						if len(data) < 2:
							continue

						if (_dir == -1 and selector_pos == 0) or (_dir == 1 and selector_pos == len(data) - 1):
							continue

						data[selector_pos], data[selector_pos + _dir] = data[selector_pos + _dir], data[selector_pos]
						conf.selectors[selector_pos], conf.selectors[selector_pos + _dir] = conf.selectors[selector_pos + _dir], conf.selectors[selector_pos]
						conf._set_dirty('selectors')
						await conf.update()

						pointer[0] += _dir

					# move roles
					else:
						role_pos = pointer[1]

						roles = data[pointer[0]]['roles']

						if len(roles) < 2:
							continue

						if (_dir == -1 and role_pos == 0) or (_dir == 1 and role_pos == len(roles) - 1):
							continue

						roles[role_pos], roles[role_pos + _dir] = roles[role_pos + _dir], roles[role_pos]
						await self._reorder_selector(data[pointer[0]]['id'], roles)

						pointer[1] += _dir

"""

def setup(bot):
	bot.add_cog(Roles(bot))

"""
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


"""