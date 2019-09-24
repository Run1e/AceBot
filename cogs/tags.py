import discord
import logging
import asyncio
import asyncpg

from discord.ext import commands
from datetime import datetime

from cogs.mixins import AceMixin
from utils.time import pretty_datetime
from utils.pager import Pager
from utils.prompter import admin_prompter, ADMIN_PROMPT_ABORTED
from utils.checks import is_mod_pred


log = logging.getLogger(__name__)


def build_tag_name(record):
	name = record.get('name')
	if record.get('alias') is not None:
		name += f" ({record.get('alias')})"
	return name


class TagCreateConverter(commands.Converter):
	_length_max = 32
	_length_min = 2

	_reserved = (
		'tag',
		'create', 'add', 'new',
		'edit', 'raw',
		'delete', 'remove',
		'list', 'all', 'browse',
		'make',
		'raw',
		'rename',
		'alias',
		'transfer',
		'search', 'find',
		'info', 'stats',
		'top', 'get', 'set', 'put', 'exec'
	)

	async def convert(self, ctx, tag_name):
		tag_name = tag_name.lower()

		if len(tag_name) > self._length_max:
			raise commands.CommandError(f'Tag name limit is {self._length_max} characters.')
		if len(tag_name) < self._length_min:
			raise commands.CommandError(f'Tag names must be at least {self._length_min} characters long.')
		if tag_name in self._reserved:
			raise commands.CommandError('Sorry, that tag name is reserved.')

		escape_converter = commands.clean_content(fix_channel_mentions=True, escape_markdown=True)
		if tag_name != await escape_converter.convert(ctx, tag_name):
			raise commands.CommandError('Tag name has disallowed formatting in it.')

		if ctx.cog.tag_is_being_made(ctx, tag_name):
			raise commands.CommandError('Tag is currently being made elsewhere.')

		exist_id = await ctx.bot.db.fetchval(
			'SELECT id FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if exist_id is not None:
			raise commands.CommandError('Tag name is already in use.')

		return tag_name


class TagEditConverter(commands.Converter):
	ACCESS_ERROR = commands.CommandError('Tag not found or you do not have edit permissions for it.')

	async def convert(self, ctx, tag_name):
		tag_name = tag_name.lower()

		rec = await ctx.bot.db.fetchrow(
			'SELECT * FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if rec is None:
			raise self.ACCESS_ERROR

		# check if invoker owns tag
		if rec.get('user_id') != ctx.author.id:

			# if not, and user is not moderator, raise access error
			if not await is_mod_pred(ctx):
				raise self.ACCESS_ERROR

			# if user is moderator, run the admin prompt
			if not await admin_prompter(ctx):
				# if it returns false, abort
				raise ADMIN_PROMPT_ABORTED

		return tag_name, rec


class TagViewConverter(commands.Converter):
	async def convert(self, ctx, tag_name):
		tag_name = tag_name.lower()

		rec = await ctx.bot.db.fetchrow(
			'SELECT * FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if rec is not None:
			return tag_name, rec

		# otherwise, find a list of potential matches

		similars = await ctx.bot.db.fetch(
			'SELECT name, alias FROM tag WHERE guild_id=$1 AND (name % $2 OR alias % $2) LIMIT 5',
			ctx.guild.id, tag_name
		)

		if similars:
			tag_list = '\n'.join(build_tag_name(record) for record in similars)
			raise commands.CommandError(f'Tag not found. Did you mean any of these?\n\n{tag_list}')

		# and if none found, just raise the not found error
		raise commands.CommandError('Tag not found.')


class TagPager(Pager):
	member = None

	async def craft_page(self, e, page, entries):
		e.set_author(
			name=self.member.display_name if self.member else self.ctx.guild.name,
			icon_url=self.member.avatar_url if self.member else self.ctx.guild.icon_url
		)

		e.description = f'{len(self.entries)} total tags.'

		names, aliases, uses = zip(*entries)

		tags = ''
		for idx, name in enumerate(names):
			tags += f'\n{name}'
			alias = aliases[idx]
			if alias is not None:
				tags += f' ({alias})'

		e.add_field(name='Name', value=tags[1:])
		e.add_field(name='Uses', value='\n'.join(str(use) for use in uses))


class Tags(AceMixin, commands.Cog):
	'''Store and bring up text using tags.'''

	def __init__(self, bot):
		super().__init__(bot)

		self._being_made = dict()

	async def bot_check(self, ctx):
		try:
			being_made = self._being_made[ctx.guild.id]
		except KeyError:
			return True

		return (ctx.channel.id, ctx.author.id) not in being_made

	def tag_is_being_made(self, ctx, tag_name):
		try:
			being_made = self._being_made[ctx.guild.id]
		except KeyError:
			return False

		return tag_name in being_made.values()

	def set_tag_being_made(self, ctx, tag_name):
		key = (ctx.channel.id, ctx.author.id)

		if ctx.guild.id in self._being_made:
			self._being_made[ctx.guild.id][key] = tag_name
		else:
			self._being_made[ctx.guild.id] = {key: tag_name}

	def unset_tag_being_made(self, ctx):
		try:
			being_made = self._being_made[ctx.guild.id]
		except KeyError:
			return

		being_made.pop((ctx.channel.id, ctx.author.id))
		if not being_made:
			self._being_made.pop(ctx.guild.id)

	def craft_tag_contents(self, ctx, content):
		if ctx.message.attachments:
			content = content or ''
			content += ('\n' if len(content) else '') + ctx.message.attachments[0].url

		if content is None:
			raise commands.UserInputError('content is a required argument that is missing.')

		return content

	async def create_tag(self, ctx, tag_name, content):
		try:
			await self.db.execute(
				'INSERT INTO tag (name, guild_id, user_id, created_at, content) VALUES ($1, $2, $3, $4, $5)',
				tag_name, ctx.guild.id, ctx.author.id, datetime.utcnow(), content
			)
		except asyncpg.UniqueViolationError:
			raise commands.CommandError('Tag already exists.')
		except Exception:
			raise commands.CommandError('Failed to create tag for unknown reasons.')

	@commands.group(invoke_without_command=True)
	async def tag(self, ctx, *, tag_name: TagViewConverter):
		'''Retrieve a tags content.'''

		tag_name, record = tag_name
		await ctx.send(record.get('content'))

		await self.db.execute(
			'UPDATE tag SET uses=$2, viewed_at=$3 WHERE id=$1',
			record.get('id'), record.get('uses') + 1, datetime.utcnow()
		)

	@tag.command(aliases=['add', 'new'])
	async def create(self, ctx, tag_name: TagCreateConverter, *, content: commands.clean_content = None):
		'''Create a new tag.'''

		await self.create_tag(ctx, tag_name, self.craft_tag_contents(ctx, content))
		await ctx.send(f'Tag \'{tag_name}\' created.')

	@tag.command()
	async def edit(self, ctx, tag_name: TagEditConverter, *, new_content: commands.clean_content = None):
		'''Edit an existing tag.'''

		tag_name, record = tag_name

		new_content = self.craft_tag_contents(ctx, new_content)

		await self.db.execute(
			'UPDATE tag SET content=$2, edited_at=$3 WHERE id=$1',
			record.get('id'), new_content, datetime.utcnow()
		)

		await ctx.send(f"Tag \'{record.get('name')}\' edited.")

	@tag.command(aliases=['remove'])
	async def delete(self, ctx, *, tag_name: TagEditConverter):
		'''Delete a tag.'''

		tag_name, record = tag_name
		await self.db.execute('DELETE FROM tag WHERE id=$1', record.get('id'))

		await ctx.send(f"Tag \'{record.get('name')}\' deleted.")

	@tag.command(name='list', aliases=['all', 'browse'])
	@commands.bot_has_permissions(embed_links=True)
	async def _list(self, ctx, *, member: discord.Member = None):
		'''List all server tags, or a members tags.'''

		if member is None:
			tags = await self.db.fetch(
				'SELECT name, alias, uses FROM tag WHERE guild_id=$1 ORDER BY uses DESC',
				ctx.guild.id
			)
		else:
			tags = await self.db.fetch(
				'SELECT name, alias, uses FROM tag WHERE guild_id=$1 AND user_id=$2 ORDER BY uses DESC',
				ctx.guild.id, member.id
			)

		if not tags:
			raise commands.CommandError('No tags found.')

		tag_list = [(record.get('name'), record.get('alias'), record.get('uses')) for record in tags]

		p = TagPager(ctx, tag_list)
		p.member = member

		await p.go()

	@tag.command()
	async def make(self, ctx):
		'''Interactively create a tag.'''

		def msg_check(message):
			return message.channel is ctx.channel and message.author is ctx.author

		name = None
		content = None

		self.set_tag_being_made(ctx, name)

		name_prompt = 'What would you like the name of your tag to be?'

		await ctx.send('Hi there! ' + name_prompt)

		while True:
			try:
				message = await ctx.bot.wait_for('message', check=msg_check, timeout=360.0)
			except asyncio.TimeoutError:
				await ctx.send(
					'The tag make command timed out. Please try again by doing '
					'`{}tag make`'.format(ctx.prefix)
				)

				self.unset_tag_being_made(ctx)
				return

			if message.content == '{}abort'.format(ctx.prefix):
				await ctx.send('Tag creation aborted.')
				self.unset_tag_being_made(ctx)
				return

			if name is None:
				try:
					old_message = ctx.message
					ctx.message = message
					await TagCreateConverter().convert(ctx, message.content)
					ctx.message = old_message
				except commands.CommandError as exc:
					await ctx.send('Sorry! {} {}'.format(str(exc), name_prompt))
					continue

				name = message.content.lower()
				self.set_tag_being_made(ctx, name)

				await ctx.send(
					'Great! The tag name is `{}`. What would you like the tags content to be?\n'.format(name) +
					'You can abort the tag creation by sending `{}abort` at any time.'.format(ctx.prefix)
				)

				continue

			if content is None:
				old_message = ctx.message
				ctx.message = message
				content = self.craft_tag_contents(ctx, await commands.clean_content().convert(ctx, message.content))
				ctx.message = old_message
				break

		self.unset_tag_being_made(ctx)
		await self.create_tag(ctx, name, content)

		await ctx.send('Tag `{0}` created! Bring up the tag contents by doing `{1}tag {0}`'.format(name, ctx.prefix))

	@tag.command()
	async def raw(self, ctx, *, tag_name: TagViewConverter):
		'''View raw contents of a tag. Useful when editing tags.'''

		tag_name, record = tag_name
		await ctx.send(discord.utils.escape_markdown(record.get('content')))

	@tag.command()
	async def rename(self, ctx, old_name: TagEditConverter, *, new_name: TagCreateConverter):
		'''Rename a tag.'''

		old_name, record = old_name

		await self.db.execute(
			'UPDATE tag SET name=$2 WHERE id=$1',
			record.get('id'), new_name
		)

		await ctx.send(f"Tag \'{record.get('name')}\' renamed to \'{new_name}\'.")

	@tag.command()
	async def alias(self, ctx, tag_name: TagEditConverter, *, alias: TagCreateConverter = None):
		'''Give a tag an alias. Omit the alias parameter to clear existing alias.'''

		tag_name, record = tag_name

		await self.db.execute(
			'UPDATE tag SET alias=$2 WHERE id=$1',
			record.get('id'), alias
		)

		if alias is None:
			await ctx.send(f"Alias cleared for \'{record.get('name')}\'")
		else:
			await ctx.send(f"Alias for \'{record.get('name')}\' set to \'{alias}\'")

	@tag.command(aliases=['stats'])
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, *, tag_name: TagViewConverter):
		'''See stats about a tag.'''

		tag_name, record = tag_name

		owner = ctx.guild.get_member(record.get('user_id'))

		if owner is None:
			nick = 'User not found'
			avatar = ctx.guild.icon_url
		else:
			nick = owner.display_name
			avatar = owner.avatar_url

		e = discord.Embed(
			description=f"**{record.get('name')}**",
		)

		e.set_author(name=nick, icon_url=avatar)
		e.add_field(name='Owner', value=owner.mention if owner else nick)

		rank = await self.db.fetchval(
			'SELECT COUNT(id) FROM tag WHERE guild_id=$1 AND uses > $2',
			ctx.guild.id, record.get('uses') + 1
		)

		e.add_field(name='Rank', value=f'#{rank + 1}')

		e.add_field(name='Uses', value=record.get('uses'))

		if record.get('alias') is not None:
			e.add_field(name='Alias', value=record.get('alias'))

		e.add_field(name='Created at', value=pretty_datetime(record.get('created_at')))

		if record.get('viewed_at'):
			e.add_field(name='Last viewed at', value=pretty_datetime(record.get('viewed_at')))

		if record.get('edited_at'):
			e.add_field(name='Last edited at', value=pretty_datetime(record.get('edited_at')))

		await ctx.send(embed=e)

	@tag.command()
	async def transfer(self, ctx, tag_name: TagEditConverter, *, new_owner: discord.Member):
		'''Transfer a tag to another member.'''

		tag_name, record = tag_name

		if new_owner.bot:
			raise commands.CommandError('Can\'t transfer tag to bot.')

		if record.get('user_id') == new_owner.id:
			raise commands.CommandError('User already owns tag.')

		res = await self.db.execute('UPDATE tag SET user_id=$1 WHERE id=$2', new_owner.id, record.get('id'))

		if res == 'UPDATE 1':
			await ctx.send('Tag \'{}\' transferred to \'{}\''.format(record.get('name'), new_owner.display_name))
		else:
			raise commands.CommandError('Unknown error occured.')

	@tag.command(aliases=['find'])
	@commands.bot_has_permissions(embed_links=True)
	async def search(self, ctx, *, query: str):
		'''Search for a tag.'''

		similars = await ctx.bot.db.fetch(
			'SELECT name, alias FROM tag WHERE guild_id=$1 AND (name % $2 OR alias % $2) LIMIT 5',
			ctx.guild.id, query
		)

		if not similars:
			raise commands.CommandError('No approximate matches found.')

		tag_list = '\n'.join(build_tag_name(record) for record in similars)

		await ctx.send(embed=discord.Embed(description=tag_list))

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def tags(self, ctx, member: discord.Member = None):
		'''View your or someone elses tags.'''

		await ctx.invoke(self._list, member=member or ctx.author)


def setup(bot):
	bot.add_cog(Tags(bot))
