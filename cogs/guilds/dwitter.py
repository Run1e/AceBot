import discord
from discord.ext import commands

import re
from peewee import *

db = SqliteDatabase('lib/dwitter_top.db')

class Dwitter:
	"""Commands for the Dwitter server."""

	def __init__(self, bot):
		self.bot = bot

	async def __local_check(self, ctx):
		return ctx.guild.id in (395956681793863690,) or await self.bot.is_owner(ctx.author)

	async def on_message(self, message):
		# ignore messages that start with a prefix
		if message.content.startswith(tuple(await self.bot.get_prefix(message))):
			return

		# get context and do checks
		ctx = await self.bot.get_context(message)
		if not (await self.__local_check(ctx) and await self.bot.can_run(ctx)):
			return

		# find links in message
		try:
			links = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)
		except:
			return

		# loop through links and send previews if applicable
		for index, link in enumerate(links):
			if (index > 2):
				break
			if re.match("^https?://(www.)?dwitter.net/d/\d{2,}$", link):
				await self.dwitterlink(ctx, link)

	async def dwitterlink(self, ctx, link):
		split = link.split('/')
		id = split[len(split) - 1]

		try:
			dwit = Dweet.get(Dweet.id == id)
		except Dweet.DoesNotExist:
			dwit = Dweet.create(id=id)

		dwit.count += 1
		dwit.save()

	@commands.command()
	async def top(self, ctx):
		"""Get a list of the most referenced Dweets."""

		list = Dweet.select().order_by(Dweet.count.desc())

		ids, counts = '', ''
		for index, dwit in enumerate(list):
			if (index > 4):
				break
			ids += f'\n[{dwit.id}](https://www.dwitter.net/d/{dwit.id})'
			counts += f'\n{dwit.count}'

		e = discord.Embed()

		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)

		e.add_field(name='Dweet', value=ids, inline=True)
		e.add_field(name='Times linked', value=counts, inline=True)

		await ctx.send(embed=e)


class Dweet(Model):
	id = IntegerField(primary_key=True)
	count = IntegerField(default=0)

	class Meta:
		database = db

def setup(bot):
	db.connect()
	db.create_tables([Dweet], safe=True)
	bot.add_cog(Dwitter(bot))