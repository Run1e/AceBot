import discord
from discord.ext import commands

import unicodedata
import datetime
from peewee import *

db = SqliteDatabase('lib/tags.db')

class Tags:
	"""Tag system."""

	def __init__(self, bot):
		self.bot = bot
		self.reserved_names = ['create', 'edit', 'delete', 'info']

	async def get_tag(self, tag_name, guild_id, alias=True):
		for tag_obj in Tag.select().where(Tag.guild == guild_id):
			if canonical_caseless(tag_name) == canonical_caseless(tag_obj.name):
				return tag_obj
			if alias and canonical_caseless(tag_name) == canonical_caseless(tag_obj.alias):
				return tag_obj
		return None

	def name_ban(self, tag_name):
		if len(tag_name) < 2:
			return 'Tag name too short.'
		if len(tag_name) > 16:
			return 'Tag name too long.'
		if canonical_caseless(tag_name) in (canonical_caseless(name) for name in self.reserved_names):
			return f"Tag name '{tag_name}' is reserved."
		return None


	@commands.group(aliases=['t'])
	async def tag(self, ctx):
		"""Create tags."""

		# send tag
		if ctx.invoked_subcommand is None:
			tag_name = ctx.message.content[ctx.message.content.find(' ') + 1:]
			get_tag = await self.get_tag(tag_name, ctx.guild.id)

			if get_tag is None:
				return

			get_tag.uses += 1
			get_tag.save()

			await ctx.send(get_tag.content)

	@tag.group()
	async def create(self, ctx, tag_name: str, *, content: str):
		"""Create a tag."""
		ban = self.name_ban(tag_name)
		if ban:
			return await ctx.send(ban)

		if await self.get_tag(tag_name, ctx.guild.id):
			return await ctx.send(f"Tag '{tag_name}' already exists.")

		date = datetime.datetime.now()
		new_tag = Tag(name=tag_name, content=content, owner=ctx.author.id, guild=ctx.guild.id, created_at=date, edited_at=date, uses=0, alias='')
		new_tag.save()

		await ctx.send(f"Tag '{tag_name}' created.")

	@tag.group()
	async def edit(self, ctx, tag_name: str, *, new_content: str):
		get_tag = await self.get_tag(tag_name, ctx.guild.id)

		if get_tag is None:
			return await ctx.send('Could not find tag.')

		if not get_tag.owner == ctx.author.id:
			return await ctx.send('You do not own this tag.')

		get_tag.content = new_content
		get_tag.edited_at = datetime.datetime.now()
		get_tag.save()

		await ctx.send('Tag edited.')

	@tag.group()
	async def delete(self, ctx, *, tag_name: str):
		get_tag = await self.get_tag(tag_name, ctx.guild.id)

		if get_tag is None:
			return await ctx.send('Could not find tag.')

		if not get_tag.owner == ctx.author.id: # or not await self.bot.is_owner(ctx.author):
			return await ctx.send('You do not own this tag.')

		deleted = get_tag.delete_instance()

		if not deleted:
			await ctx.send('Deleting of tag failed.')
		else:
			await ctx.send(f"Tag '{get_tag.name}' deleted.")

	@tag.group()
	async def alias(self, ctx, tag_name: str, alias: str):
		get_tag = await self.get_tag(tag_name, ctx.guild.id, alias=False)

		if get_tag is None:
			return await ctx.send('Could not find tag.')

		ban = self.name_ban(alias)
		if ban:
			return await ctx.send(ban)

		get_tag.alias = alias
		get_tag.save()

		await ctx.send(f"Set alias for '{get_tag.name}' to '{alias}'")

	@tag.group()
	async def info(self, ctx, *, tag_name: str):
		get_tag = await self.get_tag(tag_name, ctx.guild.id)

		if get_tag is None:
			return await ctx.send("Could not find tag.")

		created_at = str(get_tag.created_at)[0: str(get_tag.created_at).find('.')]
		edited_at = str(get_tag.edited_at)[0: str(get_tag.edited_at).find('.')]
		edited_at = None if created_at == edited_at else edited_at

		member = ctx.guild.get_member(get_tag.owner)

		if member is None:
			nick = 'User not found'
			avatar = ctx.guild.icon_url
		else:
			nick = member.display_name
			avatar = member.avatar_url

		e = discord.Embed()
		e.description = f'**{get_tag.name}**'
		e.set_author(name=nick, icon_url=avatar)
		e.add_field(name='Owner', value=member.mention if member else nick)
		e.add_field(name='Uses', value=get_tag.uses)
		if get_tag.alias:
			e.add_field(name='Alias', value=get_tag.alias)

		footer = f'Created at: {created_at}'
		if edited_at:
			footer += f' (edited: {edited_at})'

		e.set_footer(text=footer)

		await ctx.send(embed=e)


class Tag(Model):
	name = CharField()
	content = TextField()
	owner = IntegerField()
	guild = IntegerField()
	created_at = DateTimeField()
	edited_at = DateTimeField()
	uses = IntegerField()
	alias = CharField()

	class Meta:
		database = db

def NFD(text):
	return unicodedata.normalize('NFD', text)

def canonical_caseless(text):
	return NFD(NFD(text).casefold())

def match_nocase(s1, s2):
	return canonical_caseless(s1) == canonical_caseless(s2)

def setup(bot):
	db.connect()
	try:
		db.create_tables([Tag])
	except:
		pass

	bot.add_cog(Tags(bot))