import discord, string, asyncio
from discord.ext import commands

from random import sample, choice

# https://stackoverflow.com/questions/9647202/ordinal-numbers-replacement
import math
ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(math.floor(n/10)%10!=1)*(n%10<4)*n%10::4])

phonetics = (
	('alpha', 'alfa'), 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel', 'india', ('juliet', 'juliett'),
	'kilo', 'lima', 'mike', 'november', 'oscar', 'papa', 'quebec', 'romeo', 'sierra', 'tango', 'uniform', 'victor',
	('whiskey', 'whisky'), ('x-ray', 'xray'), 'yankee', 'zulu'
)

letters = list(string.ascii_lowercase)
nato = {x[0]: x[1] for x in zip(letters, phonetics)}

months = (
	'january', 'february', 'march', 'april', 'may', 'june', 'july',
	'august', 'september', 'october', 'november', 'december'
)

class Quizzes:
	'''Collection of quizzes to make you smarter.'''

	def __init__(self, bot):
		self.bot = bot

	@commands.command(aliases=['months'], hidden=True)
	async def month(self, ctx):
		'''Learn the months?'''

		other, answer = sample(range(0, 11), k=2)

		if choice((False, True)):
			await ctx.send(f'What month is {abs(other - answer)} months {"before" if other > answer else "after"} {months[other]}?')
		else:
			await ctx.send(f'What is the {ordinal(answer + 1)} month?')

		def check(m):
			return m.channel == ctx.channel and m.author == ctx.author

		try:
			msg = await self.bot.wait_for('message', check=check, timeout=60.0)
		except asyncio.TimeoutError:
			await ctx.send(f'Sorry {ctx.author.mention}, time ran out!')
			return

		if msg.content.lower() == months[answer]:
			await ctx.send('Correct! ✅')
		else:
			await ctx.send(f'Sorry, the correct answer was {months[answer].title()}')

	@commands.command()
	async def nato(self, ctx, count: int = 3):
		'''Learn the NATO phonetic alphabet.'''

		if count < 1:
			raise commands.CommandError('Please pick a length larger than 0.')

		if count > 16:
			raise commands.CommandError('Sorry, please pick lengths lower or equal to 16.')

		lets = sample(letters, k=count)

		await ctx.send(f'**{"".join(lets).upper()}**?')

		def check(m):
			return m.channel == ctx.channel and m.author == ctx.author

		try:
			msg = await self.bot.wait_for('message', check=check, timeout=60.0)
		except asyncio.TimeoutError:
			await ctx.send(f'Sorry {ctx.author.mention}, time ran out!')
			return

		answer = msg.content.lower().split()

		async def failed():
			right = []
			for let in lets:
				asd = nato[let]
				right.append(asd[0] if isinstance(asd, tuple) else asd)
			await ctx.send(f'Sorry, that was wrong! The correct answer was `{" ".join(right).upper()}`')

		for index, part in enumerate(answer):
			answer = nato[lets[index]]
			if isinstance(answer, tuple):
				if part not in answer:
					return await failed()
			else:
				if part != answer:
					return await failed()

		await ctx.send('Correct! ✅')


def setup(bot):
	bot.add_cog(Quizzes(bot))
