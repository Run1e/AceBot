import discord
import logging

from discord.ext import commands
from datetime import datetime

from cogs.mixins import AceMixin
from utils.time import pretty_datetime
from utils.pager import Pager
from utils.prompter import admin_prompter
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
		'info', 'stat', 'stats',
		'top', 'get', 'set', 'put', 'exec', 'search',
	)

	async def convert(self, ctx, tag_name: str):
		tag_name = tag_name.lower()

		if len(tag_name) > self._length_max:
			raise commands.CommandError(f'Tag name limit is {self._length_max} characters.')
		if len(tag_name) < self._length_min:
			raise commands.CommandError(f'Tag names must be at least {self._length_min} characters long.')
		if tag_name in self._reserved:
			raise commands.CommandError('Sorry, that tag name is reserved.')
		if tag_name != discord.utils.escape_markdown(tag_name):
			raise commands.CommandError('Markdown not allowed in tag names.')

		exist_id = await ctx.bot.db.fetchval(
			'SELECT id FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if exist_id is not None:
			raise commands.CommandError('Tag name is already in use.')

		return tag_name


class TagEditConverter(commands.Converter):
	access_error = commands.CommandError('Tag not found or you do not have edit permissions for it.')

	async def convert(self, ctx, tag_name: str):
		tag_name = tag_name.lower()

		rec = await ctx.bot.db.fetchrow(
			'SELECT * FROM tag WHERE guild_id=$1 AND (name=$2 OR alias=$2)',
			ctx.guild.id, tag_name
		)

		if rec is None:
			raise self.access_error

		if rec.get('user_id') != ctx.author.id:
			if await is_mod_pred(ctx) and await admin_prompter(ctx):
				return tag_name, rec
			else:
				raise self.access_error

		return tag_name, rec


class TagViewConverter(commands.Converter):
	async def convert(self, ctx, tag_name: str):
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
	async def create(self, ctx, tag_name: TagCreateConverter, *, content: str):
		'''Create a new tag.'''

		await self.db.execute(
			'INSERT INTO tag (name, guild_id, user_id, created_at, content) VALUES ($1, $2, $3, $4, $5)',
			tag_name, ctx.guild.id, ctx.author.id, datetime.utcnow(), discord.utils.escape_mentions(content)
		)

		await ctx.send(f'Tag \'{tag_name}\' created.')

	@tag.command()
	async def edit(self, ctx, tag_name: TagEditConverter, *, new_content: str):
		'''Edit an existing tag.'''

		tag_name, record = tag_name

		await self.db.execute(
			'UPDATE tag SET content=$2, edited_at=$3 WHERE id=$1',
			record.get('id'), discord.utils.escape_mentions(new_content), datetime.utcnow()
		)

		await ctx.send(f"Tag \'{record.get('name')}\' edited.")

	@tag.command(aliases=['remove'])
	async def delete(self, ctx, *, tag_name: TagEditConverter):
		'''Delete a tag.'''

		tag_name, record = tag_name
		await self.db.execute('DELETE FROM tag WHERE id=$1', record.get('id'))

		await ctx.send(f"Tag \'{record.get('name')}\' deleted.")

	@tag.command(name='list', aliases=['all', 'browse'])
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

	@tag.command()
	async def transfer(self, ctx, tag_name: TagEditConverter, *, new_owner: discord.Member):
		'''Transfer a tag to another member.'''

		tag_name, record = tag_name

		if record.get('user_id') == new_owner.id:
			raise commands.CommandError('User already owns tag.')

		res = await self.db.execute('UPDATE tag SET user_id=$1 WHERE id=$2', new_owner.id, record.get('id'))

		if res == 'UPDATE 1':
			await ctx.send('Tag \'{}\' transferred to \'{}\''.format(record.get('name'), new_owner.display_name))
		else:
			raise commands.CommandError('Unknown error occured.')

	@tag.command()
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

	@tag.command(aliases=['stat', 'stats'])
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
			timestamp=record.get('created_at')
		)

		e.set_author(name=nick, icon_url=avatar)
		e.set_footer(text='Created')
		e.add_field(name='Owner', value=owner.mention if owner else nick)

		rank = await self.db.fetchval(
			'SELECT COUNT(id) FROM tag WHERE guild_id=$1 AND uses > $2',
			ctx.guild.id, record.get('uses') + 1
		)

		e.add_field(name='Rank', value=f'#{rank + 1}')

		e.add_field(name='Uses', value=record.get('uses'))

		if record.get('alias') is not None:
			e.add_field(name='Alias', value=record.get('alias'))

		if record.get('viewed_at'):
			e.add_field(name='Last viewed at', value=pretty_datetime(record.get('viewed_at')))

		if record.get('edited_at'):
			e.add_field(name='Last edited at', value=pretty_datetime(record.get('edited_at')))

		await ctx.send(embed=e)

	@commands.command()
	async def tags(self, ctx, member: discord.Member = None):
		'''View your or someone elses tags.'''

		await ctx.invoke(self._list, member=member or ctx.author)


def setup(bot):
	bot.add_cog(Tags(bot))
