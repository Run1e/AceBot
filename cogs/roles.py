import asyncio
import logging

import discord
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.configtable import ConfigTable
from utils.context import can_prompt
from utils.converters import EmojiConverter, MaxLengthConverter
from utils.string import po, shorten

log = logging.getLogger(__name__)

RERUN_PROMPT = 'Re-run `roles spawn` for changes to take effect.'

UP_EMOJI = '🔼'
DOWN_EMOJI = '🔽'
MOVEUP_EMOJI = '⏫'
MOVEDOWN_EMOJI = '⏬'
ADD_ROLE_EMOJI = '🇷'
ADD_SEL_EMOJI = '🇸'
DEL_EMOJI = '➖'
EDIT_EMOJI = '✏️'
SAVE_EMOJI = '💾'
ABORT_EMOJI = '🚮'

EMBED_EMOJIS = (
	ADD_SEL_EMOJI, ADD_ROLE_EMOJI, UP_EMOJI, DOWN_EMOJI,
	MOVEUP_EMOJI, MOVEDOWN_EMOJI, EDIT_EMOJI, DEL_EMOJI, ABORT_EMOJI, SAVE_EMOJI
)


class SelectorEmojiConverter(EmojiConverter):
	async def convert(self, ctx, argument):
		argument = await super().convert(ctx, argument)

		if argument in (role.emoji for role in ctx.head.selector.roles):
			raise commands.CommandError('This emoji already exists in this selector.')

		return argument


role_title_converter = MaxLengthConverter(199)
role_desc_converter = MaxLengthConverter(1024)
selector_title_converter = MaxLengthConverter(256)
selector_desc_converter = MaxLengthConverter(1024)


class SelectorInlineConverter(commands.Converter):
	async def convert(self, ctx, argument):
		lowered = argument.lower()
		if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
			return True
		elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
			return False
		else:
			raise commands.CommandError('Input could not be interpreted as boolean.')


class CustomRoleConverter(commands.RoleConverter):
	async def convert(self, ctx, argument):
		try:
			role = await super().convert(ctx, argument)
		except commands.CommandError as exc:
			raise commands.CommandError(str(exc))

		if role == ctx.guild.default_role:
			raise commands.CommandError('The *everyone* role is not allowed.')

		if role.id in (other_role.role_id for selector in ctx.head.selectors for other_role in selector.roles):
			raise commands.CommandError('This role already exists somewhere else.')

		if ctx.author != ctx.guild.owner and role >= ctx.author.top_role:
			raise commands.CommandError('Sorry, you can\'t add roles higher than your top role.')

		config = await ctx.bot.config.get_entry(ctx.guild.id)
		if role == config.mod_role:
			raise commands.CommandError('Can\'t add moderation role to selector.')

		return role.id


NEW_ROLE_PREDS = (
	('What role do you want to add? (Send a role mention or just the role ID)', CustomRoleConverter()),
	('What name should this role entry have?', role_title_converter),
	('What emoji should be associated with this role?', SelectorEmojiConverter()),
	('What description should this role have?', role_desc_converter),
)

NEW_SEL_PREDS = (
	('What should the name of the selector be?', selector_title_converter),
)

EDIT_FOOTER = 'Send a message with your answer! Send \'exit\' to cancel.'
RETRY_MSG = 'Please try again!'


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
	def __init__(self, role_id, name, emoji, desc):
		self.id = None
		self.role_id = role_id
		self.name = name
		self.emoji = emoji
		self.description = desc

	@classmethod
	def from_record(cls, record):
		self = cls(record.get('role_id'), record.get('name'), record.get('emoji'), record.get('description'))
		self.id = record.get('id')
		return self


class Selector(MaybeDirty, MaybeNew):
	def __init__(self, title, desc, roles: list):
		self.id = None
		self.title = title
		self.description = desc
		self.inline = True
		self.roles = roles

	@classmethod
	def from_record(cls, record, roles):
		self = cls(record.get('title'), record.get('description'), roles)
		self.inline = record.get('inline')
		self.id = record.get('id')
		return self

	def add_role(self, index, role):
		self.set_dirty()
		self.roles.insert(index, role)


class RoleHead(MaybeDirty):
	front = '-> '
	back = ' <-'

	def __init__(self, conf, selectors: list):
		self.conf = conf
		self.selectors = selectors

		self.selector_pos = 0
		self.role_pos = None

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

		selector_count = len(self.selectors)

		# if this is the last role in this selector and we're moving down
		if selector_count > 1 and direction == 1 and self.role_pos == self.role_max:
			# move the role to the first role slot in the selector below
			new_sel.add_role(0, sel.roles.pop(self.role_pos))
			self.selector_pos = new_sel_pos
			self.role_pos = 0

		# if this is the first role in this selector and we're moving up
		elif selector_count > 1 and direction == -1 and self.role_pos == 0:
			# move the role to the last role slot in the selector above
			new_role_pos = len(new_sel.roles)
			new_sel.add_role(new_role_pos, sel.roles.pop(self.role_pos))
			self.selector_pos = new_sel_pos
			self.role_pos = new_role_pos

		# otherwise, just swap the two roles in this selector
		elif len(self.selector.roles) > 1:
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
		e = discord.Embed(
			description=(
				f'{ADD_SEL_EMOJI} Add selector\n{ADD_ROLE_EMOJI} Add role\n{UP_EMOJI} {DOWN_EMOJI} Move up/down\n'
				f'{MOVEUP_EMOJI} {MOVEDOWN_EMOJI} Move item up/down\n{EDIT_EMOJI} Edit item\n'
				f'{DEL_EMOJI} Delete item\n{ABORT_EMOJI} Discard changes\n{SAVE_EMOJI} Save changes\n\nEditor:'
			)
		)

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

	async def store(self, ctx):
		db = ctx.bot.db

		# delete role entries

		selector_ids = list(selector.id for selector in self.selectors if selector.id is not None)
		role_ids = list(role.id for selector in self.selectors for role in selector.roles if role.id is not None)

		# delete role entries that don't exist anymore
		await db.execute(
			'DELETE FROM role_entry WHERE guild_id=$1 AND id!=ALL($2::INTEGER[])',
			ctx.guild.id, role_ids
		)

		# delete role selectors that don't exist anymore
		await db.execute(
			'DELETE FROM role_selector WHERE guild_id=$1 AND id!=ALL($2::INTEGER[])',
			ctx.guild.id, selector_ids
		)

		sel_ids = list()

		for selector in self.selectors:
			ids = list()

			for role in selector.roles:
				if role.is_new:
					ids.append(await db.fetchval(
						'INSERT INTO role_entry (guild_id, role_id, name, emoji, description) values ($1, $2, $3, $4, $5) RETURNING id',
						ctx.guild.id, role.role_id, role.name, role.emoji, role.description
					))
				else:
					if role.dirty:
						await db.execute(
							'UPDATE role_entry SET name=$2, emoji=$3, description=$4 WHERE id=$1',
							role.id, role.name, role.emoji, role.description
						)

					ids.append(role.id)

			if selector.is_new:
				sel_ids.append(await db.fetchval(
					'INSERT INTO role_selector (guild_id, title, description, inline, roles) VALUES ($1, $2, $3, $4, $5) RETURNING id',
					ctx.guild.id, selector.title, selector.description, selector.inline, ids
				))
			else:
				if selector.dirty:
					await db.execute(
						'UPDATE role_selector SET title=$2, description=$3, inline=$4, roles=$5 WHERE id=$1',
						selector.id, selector.title, selector.description, selector.inline, ids
					)

				sel_ids.append(selector.id)

		await self.conf.update(selectors=sel_ids)


class Roles(AceMixin, commands.Cog):
	'''Create role selection menu(s).'''

	def __init__(self, bot):
		super().__init__(bot)

		self.editing = set()
		self.messages = dict()

		self.footer_tasks = dict()
		self.footer_lock = asyncio.Lock()

		self.config = ConfigTable(bot, table='role', primary='guild_id')

	async def bot_check(self, ctx):
		return (ctx.channel.id, ctx.author.id) not in self.editing

	async def cog_check(self, ctx):
		return await ctx.is_mod()

	def set_editing(self, ctx):
		self.editing.add((ctx.channel.id, ctx.author.id))

	def unset_editing(self, ctx):
		try:
			self.editing.remove((ctx.channel.id, ctx.author.id))
		except KeyError:
			pass

	@commands.group(hidden=True, invoke_without_command=True)
	async def roles(self, ctx):
		await ctx.send_help(self.roles)

	@roles.command()
	@can_prompt()
	@commands.bot_has_permissions(manage_messages=True)
	async def editor(self, ctx):
		'''Editor for selectors and roles.'''

		# ignore command input from user while editor is open
		self.set_editing(ctx)

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

			selector = Selector.from_record(slc, list(Role.from_record(role) for role in roles))
			selectors.append(selector)

		head = RoleHead(conf, selectors)

		# so converters can access the head for data integrity tests...
		ctx.head = head

		msg = await ctx.send(embed=discord.Embed(description='Please wait while reactions are being added...'))

		self.messages[ctx.guild.id] = msg

		for emoji in EMBED_EMOJIS:
			await msg.add_reaction(emoji)

		def pred(reaction, user):
			return reaction.message.id == msg.id and user.id == ctx.author.id

		async def close():
			self.unset_editing(ctx)
			try:
				await msg.delete()
				self.messages.pop(ctx.guild.id)
			except discord.HTTPException:
				pass

		while True:
			await msg.edit(embed=head.embed())

			try:
				reaction, user = await self.bot.wait_for('reaction_add', check=pred, timeout=300.0)
			except asyncio.TimeoutError:
				await close()
				raise commands.CommandError('Role editor closed after 5 minutes of inactivity.')
			else:
				await msg.remove_reaction(reaction.emoji, user)

				reac = str(reaction)

				if reac == ADD_SEL_EMOJI:
					if len(head.selectors) > 7:
						await ctx.send(
							embed=discord.Embed(description='No more than 8 selectors, sorry!'),
							delete_after=6
						)
						continue

					selector_data = await self._multiprompt(ctx, msg, NEW_SEL_PREDS)
					if selector_data is None:
						continue

					selector = Selector(selector_data[0], None, list())
					selector.set_dirty()

					new_pos = 0 if not head.selectors else head.selector_pos + 1
					head.add_selector(new_pos, selector)

					head.selector_pos = new_pos
					head.role_pos = None

				if reac == ABORT_EMOJI:
					await close()
					raise commands.CommandError('Editing aborted, no changes saved.')

				if reac == SAVE_EMOJI:
					await head.store(ctx)
					await close()
					await ctx.send('New role selectors saved. Do `roles spawn` to see!')
					break

				# rest of the actions assume at least one item (selector) is present
				if not head.selectors:
					continue

				if reac == ADD_ROLE_EMOJI:
					if len(head.selector.roles) > 24:
						await ctx.send(
							embed=discord.Embed(description='No more than 25 roles in one selector, sorry!'),
							delete_after=6
						)
						continue

					role_data = await self._multiprompt(ctx, msg, NEW_ROLE_PREDS)
					if role_data is None:
						continue

					role = Role(*role_data)

					new_pos = 0 if head.role_pos is None else head.role_pos + 1
					head.selector.add_role(new_pos, role)

					head.role_pos = new_pos

				if reac == DOWN_EMOJI:
					head.down()
				if reac == UP_EMOJI:
					head.up()

				if reac in (MOVEUP_EMOJI, MOVEDOWN_EMOJI):
					direction = -1 if reac == MOVEUP_EMOJI else 1

					if head.role_pos is None:
						head.move_selector(direction)
					else:
						head.move_role(direction)

				if reac == DEL_EMOJI:
					if head.role_pos is None:

						if len(head.selector.roles):
							p = ctx.prompt(
								'Delete selector?',
								'The selector you\'re trying to delete has {} roles inside it.'.format(
									len(head.selector.roles)
								)
							)

							if not await p:
								continue

						head.selectors.pop(head.selector_pos)
						if head.selector_pos > head.selector_max:
							head.selector_pos = head.selector_max
						head.role_pos = None

					else:
						head.selector.roles.pop(head.role_pos)
						if len(head.selector.roles) == 0:
							head.role_pos = None
						elif head.role_pos > head.role_max:
							head.role_pos = head.role_max

				if reac == EDIT_EMOJI:
					await self._edit_item(
						ctx, msg,
						head.selector if head.role_pos is None else head.selector.roles[head.role_pos]
					)

	# similarly to 'tag make', unset editing if an error occurs to not lock the users from using the bot
	@editor.error
	async def editor_error(self, ctx, error):
		self.unset_editing(ctx)

		# try to delete the embed message if it exists
		try:
			msg = self.messages.pop(ctx.guild.id)
			await msg.delete()
		except (KeyError, discord.HTTPException):
			pass

	async def _multiprompt(self, ctx, msg, preds):
		outs = list()

		def pred(message):
			return message.author.id == ctx.author.id and ctx.channel.id == ctx.channel.id

		def new_embed(question):
			e = discord.Embed(description=question)
			e.set_footer(text=EDIT_FOOTER)
			return e

		for question, conv in preds:
			try:
				await msg.edit(embed=new_embed(question))
			except discord.HTTPException:
				raise commands.CommandError('Could not replace the message embed. Did the message get deleted?')

			while True:
				try:
					message = await self.bot.wait_for('message', check=pred, timeout=60.0)
					await message.delete()
				except asyncio.TimeoutError:
					return None

				if message.content.lower() == 'exit':
					return None

				try:
					value = await conv.convert(ctx, message.content)
				except commands.CommandError as exc:
					if not msg.embeds:
						try:
							await msg.delete()
						except discord.HTTPException:
							pass
						raise commands.CommandError('Embed seems to have been removed, aborting.')

					e = msg.embeds[0]
					e.set_footer(text='NOTE: ' + str(exc) + ' ' + RETRY_MSG)
					await msg.edit(embed=e)
					continue

				outs.append(value)
				break

		return outs

	async def _edit_item(self, ctx, msg, item):
		if isinstance(item, Selector):
			questions = dict(
				title=selector_title_converter,
				description=selector_desc_converter,
				inline=SelectorInlineConverter(),
			)
		elif isinstance(item, Role):
			questions = dict(
				name=role_title_converter,
				description=role_desc_converter,
				emoji=SelectorEmojiConverter(),
			)
		else:
			raise TypeError('Unknown item type: ' + str(type(item)))

		opts = {emoji: q for emoji, q in zip(EMBED_EMOJIS, questions.keys())}

		opt_string = '\n'.join('{} {}'.format(key, value) for key, value in opts.items())

		e = discord.Embed(
			description='What would you like to edit?\n\n' + opt_string
		)

		e.set_footer(text=ABORT_EMOJI + ' to abort.')

		await msg.edit(embed=e)

		def reac_pred(reaction, user):
			return reaction.message.id == msg.id and user.id == ctx.author.id

		while True:
			try:
				reaction, user = await self.bot.wait_for('reaction_add', check=reac_pred, timeout=300.0)
			except asyncio.TimeoutError:
				return
			else:
				await msg.remove_reaction(reaction.emoji, user)

				reac = str(reaction)

				if reac == ABORT_EMOJI:
					return

				elif reac in opts.keys():
					attr = opts[reac]
					conv = questions[attr]
					break

				else:
					continue

		e.description = 'Please input a new value for \'{}\'.'.format(attr)
		e.set_footer(text='Send \'exit\' to abort.')
		await msg.edit(embed=e)

		def msg_pred(message):
			return message.channel.id == msg.channel.id and message.author.id == ctx.author.id

		while True:
			try:
				message = await self.bot.wait_for('message', check=msg_pred, timeout=60.0)
			except asyncio.TimeoutError:
				return

			await message.delete()

			if message.content.lower() == 'exit':
				return

			try:
				value = await conv.convert(ctx, message.content)
			except commands.CommandError as exc:
				if not msg.embeds:
					try:
						await msg.delete()
					except discord.HTTPException:
						pass
					raise commands.CommandError('Embed seems to have been removed, aborting.')

				e = msg.embeds[0]
				e.set_footer(text='NOTE: ' + str(exc) + ' ' + RETRY_MSG)
				await msg.edit(embed=e)
				continue

			setattr(item, attr, value)
			item.set_dirty()
			return

	@roles.command()
	@commands.bot_has_permissions(embed_links=True, add_reactions=True, manage_messages=True)
	async def spawn(self, ctx):
		'''Spawn role selectors.'''

		await ctx.message.delete()

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

		if not selectors:
			raise commands.CommandError('No selectors configured. Do `roles editor` to set one up.')

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

		msgs = list()

		async def delete_all():
			for m in msgs:
				try:
					await m.delete()
				except discord.HTTPException:
					pass

		self.cancel_footer(ctx.guild.id)

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

			e = discord.Embed(description=selector.get('description') or 'Click the reactions to give or remove roles.')

			icon = selector.get('icon')

			e.set_author(
				name=selector.get('title') or 'Role Selector',
				icon_url=icon if icon else ctx.guild.icon_url
			)

			for role in roles:
				e.add_field(
					name='{} {}'.format(role.get('emoji'), role.get('name')),
					value=role.get('description'),
					inline=selector.get('inline')
				)

			msg = await ctx.send(embed=e)

			msgs.append(msg)

			try:
				for role in roles:
					emoj = role.get('emoji')
					await msg.add_reaction(emoj)
			except discord.HTTPException:
				await delete_all()
				raise commands.CommandError(
					'Failed adding the emoji {}.\nIf the emoji has been deleted, change it in the editor.'.format(
						emoj
					)
				)

		await conf.update(channel_id=ctx.channel.id, message_ids=list(msg.id for msg in msgs))

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload):
		guild_id = payload.guild_id
		if guild_id is None:
			return

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
				embed=discord.Embed(
					description='Could not find role with ID {}. Has it been deleted?'.format(role_row.get('role_id'))
				),
				delete_after=30
			)
			return

		do_add = role not in member.roles

		try:
			if do_add:
				await member.add_roles(role, reason='Added through role selector')
				desc = '{}: added role {}'.format(member.display_name, role.name)
			else:
				await member.remove_roles(role, reason='Removed through role selector')
				desc = '{}: removed role {}'.format(member.display_name, role.name)
		except discord.HTTPException:
			desc = 'Unable to toggle role {}. Does the bot have Manage Roles permissions?'.format(role.name)

		await self.set_footer(message, desc)

		log.info(
			'%s %s %s %s in %s',
			'Added' if do_add else 'Removed',
			po(role),
			'to' if do_add else 'from',
			po(member),
			po(guild)
		)

	def cancel_footer(self, guild_id):
		task = self.footer_tasks.pop(guild_id, None)
		if task is not None:
			task.cancel()

	async def _set_footer_in(self, message, text='Click a reaction to add/remove roles.', wait=None):
		if wait is not None:
			await asyncio.sleep(wait)

		embed = message.embeds[0]
		embed.set_footer(text=text)

		try:
			await message.edit(embed=embed)
		except discord.HTTPException:
			pass

	async def set_footer(self, message, text, clear_after=4.0):
		async with self.footer_lock:
			guild_id = message.guild.id
			self.cancel_footer(message.guild.id)

			await self._set_footer_in(message, text)
			self.footer_tasks[guild_id] = asyncio.create_task(self._set_footer_in(message, wait=clear_after))


def setup(bot):
	bot.add_cog(Roles(bot))
