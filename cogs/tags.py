import discord
from discord.ext import commands
from sqlalchemy import and_, or_
from datetime import datetime

from utils.database import Tag
from utils.strip_markdown import strip_markdown
from cogs.base import TogglableCogMixin


def make_lower(s: str): return s.lower()

OK_EMOJI = '✅'
MAX_EMBEDS_TAGS = 10

class TagName(commands.Converter):
	
	_length_limit = 32
	_reserved = ['tag', 'create', 'edit', 'delete', 'info', 'list', 'top', 'raw', 'get', 'set', 'exec']
	
	async def convert(self, ctx, tag_name: make_lower):
		if len(tag_name) > self._length_limit:
			raise commands.CommandError(f'Tag name limit is {self._length_limit} characters.')
		if tag_name in self._reserved:
			raise commands.CommandError('Sorry, that tag name is reserved!')
		if tag_name != strip_markdown(tag_name):
			raise commands.CommandError('Markdown not allowed in tag names.')
		return tag_name
	

class Tags(TogglableCogMixin):
	'''Create and manage tags.'''
	
	async def __local_check(self, ctx):
		return await self._is_used(ctx)
	
	async def get_tag(self, guild_id, tag_name):
		return await Tag.query.where(
			and_(Tag.guild_id == guild_id,
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
				Tag.name == tag_name
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
			).order_by(
				Tag.uses.desc()
			).gino.all()
		else:
			tags = await Tag.query.where(
				Tag.guild_id == guild_id
			).order_by(
				Tag.uses.desc()
			).gino.all()
		return tags
	
	@commands.group()
	async def tag(self, ctx):
		'''Create and manage tags.'''
		
		if ctx.invoked_subcommand is not None:
			return
		
		tag_name = await TagName().convert(ctx, ctx.message.content[5:])
		
		tg = await self.get_tag(ctx.guild.id, tag_name)
		
		if tg is None:
			return
		
		await ctx.send(tg.content)
		await tg.update(uses=tg.uses + 1).apply()
		
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
		
		await ctx.message.add_reaction(OK_EMOJI)
		
	@tag.command(aliases=['remove'])
	async def delete(self, ctx, tag_name: TagName):
		'''Delete a tag.'''
		
		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError("Tag doesn't exist, or you don't own it.")
		
		if await tg.delete() == 'DELETE 1':
			await ctx.message.add_reaction(OK_EMOJI)
		else:
			raise commands.CommandError('Failed deleting tag.')
		
	@tag.command()
	async def edit(self, ctx, tag_name: TagName, *, content: commands.clean_content):
		'''Edit a tag.'''
		
		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError("Tag doesn't exist, or you don't own it.")
		
		await tg.update(
			content=content,
			edited_at=datetime.now()
		).apply()
		
		await ctx.message.add_reaction(OK_EMOJI)
	
	@tag.command()
	async def rename(self, ctx, old_name: TagName, new_name: TagName):
		'''Rename a tag.'''
		
		tg = await self.get_tag(ctx.guild.id, old_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError("Tag doesn't exist, or you don't own it.")
		
		if await self.tag_exists(ctx.guild.id, new_name):
			raise commands.CommandError('Tag with new selected name already exists.')
		
		await tg.update(
			name=new_name
		).apply()
		
		await ctx.message.add_reaction(OK_EMOJI)
		
	@tag.command()
	async def alias(self, ctx, tag_name: TagName, alias: TagName):
		'''Set an alias for a tag.'''
		
		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError("Tag doesn't exist, or you don't own it.")
		
		if await self.tag_exists(ctx.guild.id, alias):
			raise commands.CommandError('Alias already in use.')
		
		await tg.update(
			alias=alias
		).apply()
		
		await ctx.message.add_reaction(OK_EMOJI)
		
	@tag.command()
	async def transfer(self, ctx, tag_name: TagName, new_owner: discord.Member):
		'''Transfer ownership of a tag.'''
		
		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None or not self.can_edit(ctx.author.id, tg):
			raise commands.CommandError("Tag doesn't exist, or you don't own it.")
		
		await tg.update(
			owner_id=new_owner.id
		).apply()
		
		await ctx.message.add_reaction(OK_EMOJI)
	
	@tag.command()
	async def raw(self, ctx, *, tag_name: TagName):
		'''Get raw contents of a tag.'''
		
		tg = await self.get_tag(ctx.guild.id, tag_name)
		if tg is None:
			raise commands.CommandError('Tag not found.')
		
		await ctx.send(strip_markdown(tg.content))
	
	@tag.command()
	async def info(self, ctx, tag_name: TagName):
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

		footer = f'Created at: {created_at}'
		if edited_at is not None:
			footer += f' (edited: {edited_at})'

		e.set_footer(text=footer)

		await ctx.send(embed=e)

	@tag.command()
	async def list(self, ctx, member: discord.Member = None):
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
	async def tags(self, ctx, member: discord.Member = None):
		'''List a users tags.'''
		
		await ctx.invoke(self.list, member=member or ctx.author)
	
def setup(bot):
	bot.add_cog(Tags(bot))