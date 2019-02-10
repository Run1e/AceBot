import discord, asyncio
from math import ceil

REQUIRED_PERMS = ('send_messages', 'add_reactions', 'manage_messages', 'embed_links')

FIRST_EMOJI = '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}'
NEXT_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'
PREV_EMOJI = '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}'
LAST_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}'
STOP_EMOJI = '\N{BLACK SQUARE FOR STOP}'
HELP_EMOJI = '\N{WHITE QUESTION MARK ORNAMENT}'


class Pager:
	def __init__(self, ctx, entries, page=1, per_page=12, timeout=120.0, separator=' '):
		self.ctx = ctx
		self.bot = ctx.bot
		self.author = ctx.author
		self.guild = ctx.guild
		self.channel = ctx.channel
		self.entries = entries
		self.embed = discord.Embed()
		self.page = page
		self.timeout = timeout
		self.separator = separator
		self.per_page = per_page
		self.on_help = False

		self.static = False
		self.missing_perms = []

		# overrides to a static view if missing perms!
		perms = ctx.guild.me.permissions_in(ctx.channel)

		for perm in REQUIRED_PERMS:
			if not getattr(perms, perm):
				self.missing_perms.append(perm.replace('_', ' ').title())
				self.static = True

	async def go(self):
		await self.get_page(1)

		msg = await self.ctx.send(embed=self.embed)

		if self.static:
			return

		if self.top_page != 1:
			emojis = [FIRST_EMOJI, PREV_EMOJI, NEXT_EMOJI, LAST_EMOJI, STOP_EMOJI, HELP_EMOJI]
			if self.top_page == 2:
				emojis.remove(FIRST_EMOJI)
				emojis.remove(LAST_EMOJI)
			for emoji in emojis:
				await msg.add_reaction(emoji)

		def pred(reaction, user):
			return reaction.message.id == msg.id and user != self.bot.user

		while True:
			try:
				reaction, user = await self.bot.wait_for('reaction_add', check=pred, timeout=self.timeout)
			except asyncio.TimeoutError:
				break
			else:

				# just remove if it isn't authors reaction
				if user != self.author:
					await msg.remove_reaction(reaction.emoji, user)
					continue

				# if it is, and it's a stop emoji, just stop
				if reaction.emoji == STOP_EMOJI:
					await msg.delete()
					await self.ctx.message.delete()
					return

				# otherwise, delete the reaction before handling case
				await msg.remove_reaction(reaction.emoji, user)

				if reaction.emoji == NEXT_EMOJI:
					await self.next()
				elif reaction.emoji == PREV_EMOJI:
					await self.prev()
				elif reaction.emoji == FIRST_EMOJI:
					await self.first()
				elif reaction.emoji == LAST_EMOJI:
					await self.last()
				elif reaction.emoji == HELP_EMOJI:
					await self.help()
				else:
					continue

				await msg.edit(embed=self.embed)

		try:
			await msg.clear_reactions()
		except discord.NotFound:
			pass

	@property
	def top_page(self):
		if self.static:
			return 1
		return ceil(len(self.entries) / self.per_page)

	def clear_embed(self):
		e = self.embed

		e.title = None
		e.description = None
		e.set_author(name='', url='')

		e.clear_fields()

		if self.static:
			e.set_footer(text='Non-interactive! I\'m missing: ' + ', '.join(self.missing_perms))
		elif self.on_help:
			e.set_footer(text='')
		elif self.top_page > 1:
			e.set_footer(text=f'Page {self.page}/{self.top_page}')
		else:
			e.set_footer(text='')

	async def get_page(self, page):
		self.clear_embed()
		await self.craft_page(self.embed, page, self.get_page_entries(page))

	async def craft_page(self, e, page, entries):
		'''Crafts the actual embed.'''

		e.description = self.separator.join(str(entry) for entry in entries)

	def get_page_entries(self, page):
		'''Converts a page number to a range of entries.'''
		base = (page - 1) * self.per_page
		return self.entries[base:base + self.per_page]

	async def try_page(self, page):
		if self.top_page >= page >= 1:
			self.page = page
			await self.get_page(page)

	async def next(self):
		await self.try_page(self.page + 1)

	async def prev(self):
		await self.try_page(self.page - 1)

	async def first(self):
		self.page = 1
		await self.get_page(self.page)

	async def last(self):
		self.page = self.top_page
		await self.get_page(self.page)

	async def help(self):
		if self.on_help:
			self.on_help = False
			await self.get_page(self.page)
		else:
			self.on_help = True
			self.clear_embed()
			await self.help_embed(self.embed)

	async def help_embed(self, e):
		e.title = 'How to navigate this paginator!'
		e.description = 'Below is a description of what each emoji does.'

		e.add_field(name=PREV_EMOJI, value='Moves back to the previous page.')
		e.add_field(name=NEXT_EMOJI, value='Moves to the next page.')

		if self.top_page > 2:
			e.add_field(name=FIRST_EMOJI, value='Moves to the first page.')
			e.add_field(name=LAST_EMOJI, value='Moves to the last page.')

		e.add_field(name=STOP_EMOJI, value='Quits this pagination session.')
		e.add_field(name=HELP_EMOJI, value='Toggles this help message.')
