import discord
from discord.ext import commands
from sqlalchemy import and_, or_
from datetime import datetime

from utils.database import db, Tag
from utils.string_manip import strip_markdown


def make_lower(s: str): return s.lower()


MAX_EMBEDS_TAGS = 12


class TagName(commands.Converter):
	_length_max = 32
	_length_min = 2
	_reserved = ['tag', 'create', 'edit', 'delete', 'info', 'list', 'top', 'raw', 'get', 'set', 'exec', 'search']

	async def convert(self, ctx, tag_name: str):
		tag_name = tag_name.lower()
		if len(tag_name) > self._length_max:
			raise commands.CommandError(f'Tag name limit is {self._length_max} characters.')
		if len(tag_name) < 3:
			raise commands.CommandError(f'Tag names must be at least {self._length_min} characters long.')
		if tag_name in self._reserved:
			raise commands.CommandError('Sorry, that tag name is reserved!')
		if tag_name != strip_markdown(tag_name):
			raise commands.CommandError('Markdown not allowed in tag names.')
		return tag_name


class Tags:
	'''Bring up tags by doing `tag <tag_name>`'''

	def __init__(self, bot):
		self.bot = bot

	async def get_tag(self, guild_id, tag_name):
		return await Tag.query.where(
			and_(
				Tag.guild_id == guild_id,
				or_(
					Tag.name == tag_name,
					Tag.alias == tag_name
				)
			)
		).gino.first()

	async def tag_exists(self, guild_id, tag_name):
		return await Tag.query.where(
			and_(
				Tag.guild_id == guild_id,
				or_(
					Tag.name == tag_name,
					Tag.alias == tag_name
				)
			)
		).gino.scalar()

	def can_edit(self, author_id, tg):
		return tg.owner_id == author_id or self.bot.owner_id == author_id

	async def get_tags(self, guild_id, owner_id=None):
		if owner_id is not None:
			tags = await Tag.query.where(
				and_(
					Tag.guild_id == guild_id,
					Tag.owner_id == owner_id
				)
			).order_by(Tag.uses.desc()).gino.all()
		else:
			tags = await Tag.query.where(
				Tag.guild_id == guild_id
			).order_by(
				Tag.uses.desc()
			).gino.all()
		return tags

	async def tag_search(self, guild_id, search):
		query = '''
			SELECT name
			FROM tag
			WHERE guild_id = $1
			AND name % $2
			LIMIT 5
		'''

		alts = []
		for row in await db.all(query, guild_id, search):
			alts.append(row[0])

		return alts

	@commands.group()
	async def tag(self, ctx):
		'''Create and manage tags.'''

		if ctx.invoked_subcommand is not None:
			return

		tag_name = await TagName().convert(ctx, ctx.message.content[5:])

		tg = await self.get_tag(ctx.guild.id, tag_name)

		if tg is not None:
			await ctx.send(tg.content)
			await tg.update(uses=tg.uses + 1).apply()
			return

		# tag not found, do search

		alts = await self.tag_search(ctx.guild.id, tag_name)

		if not len(alts):
			raise commands.CommandError('Tag not found.')
		else:
			raise commands.CommandError('Tag not found. Did you mean any of these?\n\n' + '\n'.join(alts))

	@tag.command()
	async def search(self, ctx, *, query: str):
		'''Search for a tag.'''

		alts = await self.tag_search(ctx.guild.id, query)

		if not len(alts):
			raise commands.CommandError('Sorry, found no tags similar to that.')
		else:
			await ctx.send('I found these tags:\n\n' + '\n'.join(alts))

	@tag.command()
	async def create(self, ctx, tag_name: TagName, *, content: commands.clean_content):
		'''Create a tag.'''

		if await self.tag_exists(ctx.guild.id, tag_name):
			raise commands.CommandError('Tag already exists!')

		await Tag.create(
			name=tag_name,
			content=content,
			guild_id=ctx.guild.id,
			owner_id=ctx.author.id,
			uses=0,
			created_at=datetime.now()
		)

		await ctx.send('Tag created.')

	@tag.command(aliases=['remove'])
	async def delete(self, ctx, *, tag_name: TagName):
		'''Delete a tag.'''

		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError('Tag doesn\'t exist, or you don\'t own it.')

		if await tg.delete() == 'DELETE 1':
			await ctx.send('Tag deleted.')
		else:
			raise commands.CommandError('Failed deleting tag.')

	@tag.command()
	async def edit(self, ctx, tag_name: TagName, *, content: commands.clean_content):
		'''Edit a tag.'''

		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError('Tag doesn\'t exist, or you don\'t own it.')

		await tg.update(content=content, edited_at=datetime.now()).apply()

		await ctx.send('Tag edited.')

	@tag.command()
	async def rename(self, ctx, old_name: TagName, *, new_name: TagName):
		'''Rename a tag.'''

		tg = await self.get_tag(ctx.guild.id, old_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError('Tag doesn\'t exist, or you don\'t own it.')

		if await self.tag_exists(ctx.guild.id, new_name):
			raise commands.CommandError('Tag with new selected name already exists.')

		await tg.update(name=new_name).apply()

		await ctx.send('Tag renamed.')

	@tag.command()
	async def alias(self, ctx, tag_name: TagName, *, alias: TagName = None):
		'''Set an alias for a tag.'''

		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError('Tag doesn\'t exist, or you don\'t own it.')

		if alias is not None:
			if await self.tag_exists(ctx.guild.id, alias):
				raise commands.CommandError('Tag name already in use.')
			await tg.update(alias=alias).apply()
			await ctx.send('Alias set.')
		else:
			await tg.update(alias=None).apply()
			await ctx.send('Alias removed.')

	@tag.command()
	async def transfer(self, ctx, tag_name: TagName, *, new_owner: discord.Member):
		'''Transfer ownership of a tag.'''

		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError("Tag doesn't exist, or you don't own it.")

		await tg.update(
			owner_id=new_owner.id
		).apply()

		await ctx.send(f'Tag transferred to {new_owner.mention}')

	@tag.command()
	async def raw(self, ctx, *, tag_name: TagName):
		'''Get raw contents of a tag.'''

		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None:
			raise commands.CommandError('Tag not found.')

		await ctx.send(strip_markdown(tg.content))

	@tag.command()
	@commands.bot_has_permissions(embed_links=True)
	async def info(self, ctx, *, tag_name: TagName):
		'''Show info about a tag.'''

		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None:
			raise commands.CommandError('Tag not found.')

		created_at = str(tg.created_at)[0: str(tg.created_at).find('.')]
		if tg.edited_at is None:
			edited_at = None
		else:
			edited_at = str(tg.edited_at)[0: str(tg.edited_at).find('.')]

		member = ctx.guild.get_member(tg.owner_id)

		if member is None:
			nick = 'User not found'
			avatar = ctx.guild.icon_url
		else:
			nick = member.display_name
			avatar = member.avatar_url

		e = discord.Embed()
		e.description = f'**{tg.name}**'

		e.set_author(name=nick, icon_url=avatar)
		e.add_field(name='Owner', value=member.mention if member else nick)
		e.add_field(name='Uses', value=tg.uses)

		if not tg.alias is None:
			e.add_field(name='Alias', value=tg.alias)

		rank = await db.scalar('SELECT COUNT(id) from tag where uses > $1', tg.uses) + 1
		e.add_field(name='Rank', value=str(rank))

		footer = f'Created at: {created_at}'
		if edited_at is not None:
			footer += f' (edited: {edited_at})'

		e.set_footer(text=footer)

		await ctx.send(embed=e)

	@tag.command()
	@commands.bot_has_permissions(embed_links=True)
	async def list(self, ctx, *, member: discord.Member = None):
		'''List server or user tags.'''

		tags = await self.get_tags(ctx.guild.id, None if member is None else member.id)

		if not len(tags):
			raise commands.CommandError('No tags found!')

		names, uses, count = '', '', 0
		for index, tg in enumerate(tags):
			if (index > MAX_EMBEDS_TAGS):
				break
			count += 1
			names += f'\n{tg.name}'
			if tg.alias is not None:
				names += f' ({tg.alias})'
			uses += f'\n{tg.uses}'
			if len(names) > 920:
				break

		e = discord.Embed()
		e.add_field(name='Tag', value=names, inline=True)
		e.add_field(name='Uses', value=uses, inline=True)
		e.description = f'{count if count < MAX_EMBEDS_TAGS else MAX_EMBEDS_TAGS}/{len(tags)} tags'

		e.set_author(
			name=member.display_name if member else ctx.guild.name,
			icon_url=member.avatar_url if member else ctx.guild.icon_url
		)

		await ctx.send(embed=e)

	@commands.command()
	@commands.bot_has_permissions(embed_links=True)
	async def tags(self, ctx, *, member: discord.Member = None):
		'''List tags.'''

		await ctx.invoke(self.list, member=member or ctx.author)


def setup(bot):
	bot.add_cog(Tags(bot))
