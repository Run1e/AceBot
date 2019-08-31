import discord
import asyncio

from discord.ext import commands
from datetime import datetime, timedelta
from urllib.parse import unquote
from random import randrange
from base64 import decode
from enum import Enum

from cogs.mixins import AceMixin
from utils.configtable import ConfigTable


API_URL = 'https://opentdb.com/api.php'
QUESTION_TIMEOUT = 15.0

MULTIPLE_CHOICE_EMOJIS = {
	('1', 'one'): '1️⃣',
	('2', 'two'): '2️⃣',
	('3', 'three'): '3️⃣',
	('4', 'four'): '4️⃣'
}

BOOLEAN_MAP = {
	True: ('y', 't', '1', 'yes', 'true'),
	False: ('n', 'f', '0', 'no', 'false')
}

SCORE_POT = dict(
	easy=200,
	medium=400,
	hard=600
)

print(MULTIPLE_CHOICE_EMOJIS)


class DifficultyConverter(commands.Converter):
	valid_difficulties = ('easy', 'medium', 'hard')

	async def convert(self, ctx, argument):
		argument = argument.lower()

		if argument not in self.valid_difficulties:
			raise commands.CommandError('\'{}\' is not a valid difficulty.'.format(argument))

		return argument


class Trivia(AceMixin, commands.Cog):
	_stats_query = 'INSERT INTO trivia_stats (guild_id, user_id, question_hash, result) VALUES ($1, $2, $3, $4)'

	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(
			bot, 'trivia', ('guild_id', 'user_id'),
			dict(
				id=int,
				guild_id=int,
				user_id=int,
				correct_count=int,
				wrong_count=int,
				score=int
			)
		)

	@commands.command()
	async def trivia(self, ctx, *, difficulty: DifficultyConverter = 'medium'):
		'''Trivia time! Specify a difficulty as argument. Valid difficulties are `easy`, `medium` and `hard`.'''

		params = dict(
			amount=1,
			encode='url3986',
			difficulty=difficulty
		)

		async with self.bot.aiohttp.get(API_URL, params=params) as resp:
			if resp.status != 200:
				raise commands.CommandError('Request failed, try again later.')

			res = await resp.json()

		result = res['results'][0]
		print(result)

		question_type = result['type']
		category = unquote(result['category'])
		question = unquote(result['question'])
		question_hash = hash(question)
		correct_answer = unquote(result['correct_answer'])

		if question_type == 'multiple':
			options = list(unquote(option) for option in result['incorrect_answers'])

			correct_pos = randrange(0, len(options) + 1)
			options.insert(correct_pos, correct_answer)

			correct = list(MULTIPLE_CHOICE_EMOJIS.keys())[correct_pos]

			wrong = list()
			for idx, tup in enumerate(MULTIPLE_CHOICE_EMOJIS.keys()):
				if idx == correct_pos:
					continue
				for entry in tup:
					wrong.append(entry)

			options_string = '\n'.join(
				'{} {}'.format(emoj, option) for emoj, option in zip(MULTIPLE_CHOICE_EMOJIS.values(), options)
			)

		else:

			options_string = (
				'\N{REGIONAL INDICATOR SYMBOL LETTER Y} Yes/True\n'
				'\N{REGIONAL INDICATOR SYMBOL LETTER N} No/False'
			)

			correct = BOOLEAN_MAP[correct_answer == 'True']
			wrong = BOOLEAN_MAP[correct_answer == 'False']

		e = discord.Embed(title='Trivia!', description=category)
		e.add_field(name='Question', value='{}\n\n{}'.format(question, options_string), inline=False)

		e.set_footer(
			text='Answer by sending a message with the correct option.',
		)

		await ctx.send(embed=e)

		now = datetime.utcnow()

		def check(message):
			return message.channel == ctx.channel and message.author == ctx.author

		while True:
			try:
				msg = await self.bot.wait_for('message', check=check, timeout=QUESTION_TIMEOUT)

				if msg.content in correct:
					seconds_spent = (datetime.utcnow() - now).total_seconds()

					await self._on_correct(
						ctx,
						question_hash,
						SCORE_POT[difficulty] * (QUESTION_TIMEOUT - seconds_spent) / QUESTION_TIMEOUT
					)

					await ctx.send('Correct!')
					break

				elif msg.content in wrong:
					wrong_reply = 'Sorry, that was wrong!'

					if question_type == 'multiple':
						wrong_reply += 'The correct answer is: {}'.format(correct_answer)

					await ctx.send(wrong_reply)
					await self._on_wrong(ctx, question_hash)
					break

			except asyncio.TimeoutError:
				await ctx.send('Question timed out! Answer within {} seconds next time!'.format(int(QUESTION_TIMEOUT)))
				break

	async def _on_correct(self, ctx, question_hash, add_score):
		entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

		new_score = entry.score + add_score
		new_correct_count = entry.correct_count + 1

		await self.db.execute(
			'UPDATE trivia SET score = $1, correct_count = $2 WHERE guild_id=$3 AND user_id=$4',
			new_score, new_correct_count, ctx.guild.id, ctx.author.id
		)

		await self.db.execute(self._stats_query, ctx.guild.id, ctx.author.id, question_hash, True)

	async def _on_wrong(self, ctx, question_hash):
		await self.db.execute(self._stats_query, ctx.guild.id, ctx.author.id, question_hash, False)


def setup(bot):
	bot.add_cog(Trivia(bot))
