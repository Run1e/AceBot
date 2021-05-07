import asyncio
import logging
from datetime import datetime

import asyncpg
import discord
from discord.ext import commands

from cogs.mixins import AceMixin
from utils.context import AceContext, can_prompt
from utils.converters import LengthConverter, MaybeMemberConverter
from utils.pager import Pager
from utils.time import pretty_datetime

log = logging.getLogger(__name__)


def build_tag_name(record):
	name = record.get('name')
	if record.get('alias') is not None:
		name += f" ({record.get('alias')})"
	return name


class TagCreateConverter(LengthConverter):
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

	async def convert(self, ctx, argument):
		tag_name = await super().convert(ctx, argument.lower())

		if tag_name in self._reserved:
			raise commands.BadArgument('Sorry, that tag name is reserved.')

		escape_converter = commands.clean_content(fix_channel_mentions=True, escape_markdown=True)
		if tag_name != await escape_converter.convert(ctx, tag_name):
			raise commands.BadArgument('Tag name has disallowed formatting in it.')

		if ctx.cog.tag_is_being_made(ctx, tag_name):
			raise commands.BadArgument('Tag with that name is currently being made elsewhere.')

		exist_id = await ctx.bot.db.fetchval(
			'SELECT id FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if exist_id is not None:
			raise commands.BadArgument('Tag name is already in use.')

		return tag_name


tag_create_converter = TagCreateConverter(2, 32)

ACCESS_ERROR = commands.CommandError('Tag not found or you do not have edit permissions for it.')


class TagEditConverter(commands.Converter):
	def __init__(self, allow_mod=False):
		self.allow_mod = allow_mod

	async def convert(self, ctx, tag_name):
		tag_name = tag_name.lower()

		rec = await ctx.bot.db.fetchrow(
			'SELECT * FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if rec is None:
			raise ACCESS_ERROR

		# check if invoker owns tag. if not, check if bot owner is invoking
		if rec.get('user_id') != ctx.author.id and not await ctx.bot.is_owner(ctx.author):
			# if not, check if mod should be allowed to do this action. if not, raise access error
			# if they can, check if invoker is mod, if not, raise access error
			if not self.allow_mod or not await ctx.is_mod():
				raise ACCESS_ERROR

			# if user is moderator, run the admin prompt
			await ctx.admin_prompt(raise_on_abort=True)

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
	'''Store and bring up text using tags. Tags are unique to each server.'''

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

	async def craft_tag_contents(self, ctx, content):
		content = await commands.clean_content().convert(ctx, content)

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
	async def tag(self, ctx, *, tag_name: TagViewConverter = None):
		'''Retrieve a tags content.'''

		if tag_name is None:
			await ctx.send_help(self.tag)
			return

		tag_name, record = tag_name
		await ctx.send(record.get('content'), allowed_mentions=discord.AllowedMentions.none())

		await self.db.execute(
			'UPDATE tag SET uses=$2, viewed_at=$3 WHERE id=$1',
			record.get('id'), record.get('uses') + 1, datetime.utcnow()
		)

	@tag.command(aliases=['add', 'new'])
	async def create(self, ctx, tag_name: tag_create_converter, *, content: str = None):
		'''Create a new tag.'''

		content = await self.craft_tag_contents(ctx, content)

		await self.create_tag(ctx, tag_name, content)
		await ctx.send(f'Tag \'{tag_name}\' created.')

	@tag.command()
	@can_prompt()
	async def edit(self, ctx, tag_name: TagEditConverter(), *, new_content: str = None):
		'''Edit an existing tag.'''

		tag_name, record = tag_name

		new_content = await self.craft_tag_contents(ctx, new_content)

		await self.db.execute(
			'UPDATE tag SET content=$2, edited_at=$3 WHERE id=$1',
			record.get('id'), new_content, datetime.utcnow()
		)

		await ctx.send(f"Tag \'{record.get('name')}\' edited.")

	@tag.command(aliases=['remove'])
	@can_prompt()
	async def delete(self, ctx, *, tag_name: TagEditConverter(allow_mod=True)):
		'''Delete a tag.'''

		if not await ctx.prompt(title='Are you sure?', prompt='This will delete the tag permanently.'):
			raise commands.CommandError('Tag deletion aborted.')

		tag_name, record = tag_name
		await self.db.execute('DELETE FROM tag WHERE id=$1', record.get('id'))

		await ctx.send(f"Tag \'{record.get('name')}\' deleted.")

	@tag.command(name='list', aliases=['all', 'browse'])
	@commands.bot_has_permissions(embed_links=True)
	async def _list(self, ctx, *, member: MaybeMemberConverter = None):
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
		'''Create a tag interactively.'''

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
					await tag_create_converter.convert(ctx, message.content)
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
				content = await self.craft_tag_contents(ctx, message.content)
				ctx.message = old_message
				break

		self.unset_tag_being_made(ctx)
		await self.create_tag(ctx, name, content)

		await ctx.send('Tag `{0}` created! Bring up the tag contents by doing `{1}tag {0}`'.format(name, ctx.prefix))

	# unset tag being made if make errors out
	@make.error
	async def make_error(self, ctx, error):
		self.unset_tag_being_made(ctx)

	@tag.command()
	async def raw(self, ctx, *, tag_name: TagViewConverter()):
		'''View raw contents of a tag. Useful when editing tags.'''

		tag_name, record = tag_name
		await ctx.send(
			discord.utils.escape_markdown(record.get('content')),
			allowed_mentions=discord.AllowedMentions.none()
		)

	@tag.command()
	@can_prompt()
	async def rename(self, ctx, old_name: TagEditConverter(), *, new_name: tag_create_converter):
		'''Rename a tag.'''

		old_name, record = old_name

		await self.db.execute(
			'UPDATE tag SET name=$2 WHERE id=$1',
			record.get('id'), new_name
		)

		await ctx.send(f"Tag \'{record.get('name')}\' renamed to \'{new_name}\'.")

	@tag.command()
	@can_prompt()
	async def alias(self, ctx, tag_name: TagEditConverter(), *, alias: tag_create_converter = None):
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
	async def info(self, ctx, *, tag_name: TagViewConverter()):
		'''See tag statistics.'''

		tag_name, record = tag_name

		owner = ctx.guild.get_member(record.get('user_id'))

		if owner is None:
			nick = 'Unknown User'
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

		alias = record.get('alias')
		created_at = record.get('created_at')
		viewed_at = record.get('viewed_at')
		edited_at = record.get('edited_at')

		if alias is not None:
			e.add_field(name='Alias', value=alias)

		e.add_field(name='Created at', value=pretty_datetime(created_at))

		if viewed_at:
			e.add_field(name='Last viewed at', value=pretty_datetime(viewed_at))

		if edited_at:
			e.add_field(name='Last edited at', value=pretty_datetime(edited_at))

		await ctx.send(embed=e)

	@tag.command()
	@can_prompt()
	async def transfer(self, ctx: AceContext, tag_name: TagEditConverter(), *, new_owner: discord.Member):
		'''Transfer ownership of a tag to another member.'''

		tag_name, record = tag_name

		if new_owner.bot:
			raise commands.CommandError('Can\'t transfer tag to bot.')

		if record.get('user_id') == new_owner.id:
			raise commands.CommandError('User already owns tag.')

		prompt = ctx.prompt(
			title='Tag transfer request',
			prompt=f'{ctx.author.mention} wants to transfer ownership of the tag \'{tag_name}\' to you.\n\nDo you accept?',
			user_override=new_owner
		)

		if not await prompt:
			raise commands.CommandError('Tag transfer aborted.')

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
