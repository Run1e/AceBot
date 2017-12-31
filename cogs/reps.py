import discord
from discord.ext import commands

import random, time
from peewee import *

db = SqliteDatabase('lib/reps.db')

class Reputation:
	"""Handles the highlight command."""

	def __init__(self, bot):
		self.bot = bot
		self.timeout = 5
		self.times = {}
		self.good_emoji = ['pray', 'raised_hands', 'clap', 'ok_hand', 'tongue', 'heart_eyes']
		self.bad_emoji = ['cry', 'disappointed_relieved', 'sleepy', 'sob', 'thinking']

	@commands.command()
	async def replist(self, ctx, amount: int = 8):
		"""Show a list of the most respected users."""

		list = RepUser.select()\
			.where(RepUser.guild_id == ctx.guild.id)\
			.order_by(RepUser.count.desc())

		users, counts, added = '', '', 0
		for rep_user in list:
			if added >= amount:
				break
			user = ctx.guild.get_member(rep_user.user_id)
			if not user:
				continue
			users += f'{user.display_name}\n'
			counts += f'{rep_user.count}\n'
			added += 1

		if not added:
			return await ctx.send('No users with any reputation in this server.')

		e = discord.Embed()
		e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
		e.add_field(name='Users', value=users, inline=True)
		e.add_field(name='Reputation', value=counts, inline=True)

		await ctx.send(embed=e)

	@commands.command()
	async def rep(self, ctx, member: discord.Member = None):
		"""Send some love!"""

		# get self-rep
		if member is None:
			try:
				user = RepUser.get(RepUser.user_id == ctx.author.id, RepUser.guild_id == ctx.guild.id)
			except RepUser.DoesNotExist:
				return await ctx.send(f'You have 0 reputation... {random.choice(self.bad_emoji)}')
			return await ctx.send(f'You have {user.count} reputation! :{random.choice(self.good_emoji)}:')

		# nah fam
		if member == ctx.author:
			return await ctx.send(':japanese_goblin: :thumbsdown:')

		# time check
		try:
			since_last = time.time() - self.times[ctx.guild][ctx.author]
			if since_last < self.timeout:
				return await ctx.send(f'You have to wait {round(since_last)} more seconds until you can rep again.')
		except:
			pass

		# get user
		try:
			user = RepUser.get(RepUser.user_id == member.id, RepUser.guild_id == ctx.guild.id)
		except RepUser.DoesNotExist:
			user = RepUser.create(user_id=member.id, guild_id=ctx.guild.id)

		# increment and save
		user.count += 1
		user.save()

		# check if guild/author is in times obj
		if ctx.guild not in self.times:
			self.times[ctx.guild] = {}
			if ctx.author not in self.times[ctx.guild]:
				self.times[ctx.guild][ctx.author] = 0

		# set current time
		self.times[ctx.guild][ctx.author] = time.time()

		await ctx.send(f'{member.mention} now has {user.count} reputation! :{random.choice(self.good_emoji)}:')


class RepUser(Model):
	user_id = BigIntegerField()
	guild_id = BigIntegerField()
	count = IntegerField(default=0)

	class Meta:
		database = db
		primary_key = CompositeKey('user_id', 'guild_id')

def setup(bot):
	db.connect()
	db.create_tables([RepUser], safe=True)
	bot.add_cog(Reputation(bot))

"""
	@commands.command()
	async def rep(self, ctx, mention: discord.Member = None):
		if mention is None:
			return await ctx.send(f'{ctx.author.mention} has a reputation of {(self.reps[str(ctx.author.id)] if str(ctx.author.id) in self.reps else 0)}!')

		# get the id
		id = str(mention.id)

		# make sure people can't rep themselves
		if mention == ctx.author:
			return await ctx.send(":japanese_goblin:")

		# make sure a reptime object exists for the author
		if not ctx.author.id in self.reptime:
			self.reptime[ctx.author.id] = {}

		# make sure the repee has an entry, and if it already does, make sure it's outside of the reptime
		if not id in self.reptime[ctx.author.id]:
			self.reptime[ctx.author.id][id] = time.time()
		else:
			if time.time() - self.reptime[ctx.author.id][id] < 120:
				return await ctx.send("Woah! You shouldn't be repping *that* fast.")
			else:
				self.reptime[ctx.author.id][id] = time.time()

		# make sure the repee has a key
		if not id in self.reps:
			self.reps[id] = 0

		# increment
		self.reps[id] += 1

		# save the new json
		open('lib/rep.json', 'w').write(json.dumps(self.reps))

		if id == str(self.bot.user.id):
			await ctx.send(f'Thanks {ctx.author.mention}! I now have {self.reps[id]} rep points! :blush: ')
		else:
			emojis = ['pray', 'raised_hands', 'clap', 'ok_hand', 'tongue', 'heart_eyes']
			await ctx.send(f'{mention.mention} now has {self.reps[id]} reputation! :{random.choice(emojis)}:')

	@commands.command()
	async def replist(self, ctx, users: int = 8):
		if users > 20:
			users = 20
		elif users < 1:
			users = 2

		rep_sort = sorted(self.reps.items(), key=operator.itemgetter(1), reverse=True)

		added = 0
		names = ''
		reps = ''

		for user, rep_count in rep_sort:
			member = ctx.guild.get_member(int(user))
			if not member is None:
				names += f'*{str(member).split("#")[0]}*\n'
				reps += f'{rep_count}\n'
				added += 1
			if added == users:
				break

		e = discord.Embed()
		e.add_field(name='User', value=names, inline=True)
		e.add_field(name='Reputation', value=reps, inline=True)

		await ctx.send(embed=e)

"""