from math import ceil

import disnake

FIRST_EMOJI = '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}'
NEXT_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'
PREV_EMOJI = '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}'
LAST_EMOJI = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}'
STOP_EMOJI = '\N{BLACK SQUARE FOR STOP}'
HELP_EMOJI = '\N{WHITE QUESTION MARK ORNAMENT}'


class Pager(disnake.ui.View):
	def __init__(self, ctx, entries=None, per_page=6, timeout=180.0):
		super().__init__(timeout=timeout)

		self.ctx = ctx
		self.entries = entries
		self.per_page = per_page

		self.page = 0
		self.embed = None

	async def go(self, at_page=0):
		await self.ctx.send(embed=await self.init(at_page=at_page), view=self if self.top_page else None)

	async def init(self, at_page=0):
		self.embed = await self.create_base_embed()
		await self.try_page(at_page)

		return self.embed

	def get_page_entries(self, page):
		'''Converts a page number to a range of entries.'''
		base = page * self.per_page
		return self.entries[base:base + self.per_page]

	async def create_base_embed(self):
		raise NotImplementedError()

	async def update_page_embed(self, embed, page, entries):
		raise NotImplementedError()

	@property
	def top_page(self):
		return ceil(len(self.entries) / self.per_page) - 1

	async def try_page(self, page):
		if not 0 <= page <= self.top_page:
			return

		self.page = page

		if self.top_page:
			self.embed.set_footer(text=f'Page {page + 1}/{self.top_page + 1}')

		await self.update_page_embed(self.embed, page, self.get_page_entries(page))

	@disnake.ui.button(label='Previous page', emoji=PREV_EMOJI, style=disnake.ButtonStyle.primary, row=0)
	async def prev_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
		await self.try_page(self.page - 1)
		await inter.response.edit_message(embed=self.embed)

	@disnake.ui.button(label='Next page', emoji=NEXT_EMOJI, style=disnake.ButtonStyle.primary, row=0)
	async def next_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
		await self.try_page(self.page + 1)
		await inter.response.edit_message(embed=self.embed)

	@disnake.ui.button(label='First page', emoji=FIRST_EMOJI, style=disnake.ButtonStyle.secondary, row=1)
	async def first_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
		await self.try_page(0)
		await inter.response.edit_message(embed=self.embed)

	@disnake.ui.button(label='Last page', emoji=LAST_EMOJI, style=disnake.ButtonStyle.secondary, row=1)
	async def last_page(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
		await self.try_page(self.top_page)
		await inter.response.edit_message(embed=self.embed)

	@disnake.ui.button(label='Stop', emoji=STOP_EMOJI, style=disnake.ButtonStyle.danger, row=1)
	async def stop_pager(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
		await inter.response.edit_message(view=None)
		self.stop()
