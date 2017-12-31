import discord
from discord.ext import commands

import re
from peewee import *
from playhouse.migrate import *

db = SqliteDatabase('lib/reps.db')
migrator = SqliteMigrator(db)

class Reputation:
	"""Handles the highlight command."""

	def __init__(self, bot):
		self.bot = bot
		self.good_emoji = ['pray', 'raised_hands', 'clap', 'ok_hand', 'tongue', 'heart_eyes']
		self.bad_emoji = []

	@commands.command()
	async def rep(self, ctx, member: discord.Member = None):

		# get self-rep
		if member is None:
			try:
				user = RepUser.get(RepUser.user == ctx.author.id)
			except RepUser.DoesNotExist:
				return await ctx.send('You have 0 reputation!')

			print(user.user)
			print(user[ctx.guild.id])
			return await ctx.send('your rep here')

		# nah
		if member == ctx.author:
			return await ctx.send(':japanese_goblin:')

		has_guild = False
		for column in db.get_columns('repuser'):
			if column.name == str(ctx.guild.id):
				has_guild = True
				break

		# if not, add it to the table
		if not has_guild:
			guild_field = IntegerField(null=True)
			migrate(migrator.add_column('repuser', f'_{str(ctx.guild.id)}', guild_field))

		# rep someone else
		try:
			user = RepUser.get(RepUser.user == member.id)
		except RepUser.DoesNotExist:
			user = RepUser(user=member.id)
		print(ctx.guild.id)
		user.update(**{'_115993023636176902': 4}).execute()

		user.save()


class RepUser(Model):
	user = BigIntegerField()

	class Meta:
		database = db

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