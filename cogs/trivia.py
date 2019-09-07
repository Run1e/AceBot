import discord
import asyncio

from discord.ext import commands
from datetime import datetime
from urllib.parse import unquote
from random import randrange, choice

from cogs.mixins import AceMixin
from utils.configtable import ConfigTable


API_URL = 'https://opentdb.com/api.php'
QUESTION_TIMEOUT = 15.0

MULTIPLE_MAP = {
	('1', 'one'): '1️⃣',
	('2', 'two'): '2️⃣',
	('3', 'three'): '3️⃣',
	('4', 'four'): '4️⃣'
}

BOOLEAN_MAP = {
	('y', 'yes', 't', 'true'): '\N{REGIONAL INDICATOR SYMBOL LETTER Y}',
	('n', 'no', 'f', 'false'): '\N{REGIONAL INDICATOR SYMBOL LETTER N}'
}

SCORE_POT = dict(
	easy=250,
	medium=500,
	hard=1000
)

PENALTY_DIV = 2.2


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

		self.config = ConfigTable(bot, 'trivia', ('guild_id', 'user_id'))

	async def cog_check(self, ctx):
		return await self.bot.is_owner(ctx.author)

	@commands.group(invoke_without_command=True)
	@commands.bot_has_permissions(embed_links=True)
	async def trivia(self, ctx, *, difficulty: DifficultyConverter = None):
		'''Trivia time! Specify a difficulty as argument. Valid difficulties are `easy`, `medium` and `hard`.'''

		if difficulty is None:
			difficulty = choice(DifficultyConverter.valid_difficulties)

		params = dict(
			amount=1,
			encode='url3986',
			difficulty=difficulty,
			#type='boolean'
		)

		async with self.bot.aiohttp.get(API_URL, params=params) as resp:
			if resp.status != 200:
				raise commands.CommandError('Request failed, try again later.')

			res = await resp.json()

		result = res['results'][0]

		question_type = result['type']
		category = unquote(result['category'])
		correct_answer = unquote(result['correct_answer'])

		question = unquote(result['question'])
		question_hash = hash(question)

		if question_type == 'multiple':
			options = list(unquote(option) for option in result['incorrect_answers'])
			correct_pos = randrange(0, len(options) + 1)
			options.insert(correct_pos, correct_answer)
		else:
			options = ('True', 'False')
			correct_pos = int(correct_answer == 'False')

		option_reference = BOOLEAN_MAP if question_type == 'boolean' else MULTIPLE_MAP

		question_string = '{}\n\n{}\n'.format(
			question,
			'\n'.join('{} {}'.format(emoji, option) for emoji, option in zip(option_reference.values(), options))
		)

		e = discord.Embed(
			title='Trivia time!',
			description='**Category**: {}\n**Difficulty**: {}'.format(category, difficulty)
		)
		e.add_field(name='Question', value=question_string, inline=False)
		e.set_footer(text='Answer by sending a message with the correct option.')

		await ctx.send(embed=e)

		now = datetime.utcnow()

		def check(message):
			return message.channel == ctx.channel and message.author == ctx.author

		while True:
			try:
				msg = await self.bot.wait_for('message', check=check, timeout=QUESTION_TIMEOUT)

				for idx, responses in enumerate(option_reference.keys()):
					if msg.content.lower() in responses:
						seconds_spent = (datetime.utcnow() - now).total_seconds()
						score = int(SCORE_POT[difficulty] * (QUESTION_TIMEOUT - seconds_spent / 2) / QUESTION_TIMEOUT)

						if idx == correct_pos:
							await ctx.send('Correct! You gained {} points.'.format(score))
							await self._on_correct(ctx, question_hash, score)
						else:
							score = int(score / PENALTY_DIV)

							await ctx.send('Sorry, that was wrong! You lost {} points.'.format(score))
							await self._on_wrong(ctx, question_hash, score)

						return

			except asyncio.TimeoutError:
				await ctx.send('Question timed out. Answer within {} seconds next time!'.format(int(QUESTION_TIMEOUT)))
				return

	async def _on_correct(self, ctx, question_hash, add_score):
		entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

		new_score = entry.score + add_score
		new_correct_count = entry.correct_count + 1

		await self.db.execute(
			'UPDATE trivia SET score = $1, correct_count = $2 WHERE guild_id=$3 AND user_id=$4',
			new_score, new_correct_count, ctx.guild.id, ctx.author.id
		)

		await self.db.execute(self._stats_query, ctx.guild.id, ctx.author.id, question_hash, True)

	async def _on_wrong(self, ctx, question_hash, remove_score):
		entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

		new_score = entry.score - remove_score
		new_wrong_count = entry.wrong_count + 1

		await self.db.execute(
			'UPDATE trivia SET score = $1, wrong_count = $2 WHERE guild_id=$3 AND user_id=$4',
			new_score, new_wrong_count, ctx.guild.id, ctx.author.id
		)

		await self.db.execute(self._stats_query, ctx.guild.id, ctx.author.id, question_hash, False)

	@trivia.command()
	@commands.bot_has_permissions(embed_links=True)
	async def stats(self, ctx, *, member: discord.Member = None):
		'''Get your own or another members' trivia stats.'''

		member = member or ctx.author

		entry = await self.config.get_entry(ctx.guild.id, member.id)

		total_games = entry.correct_count + entry.wrong_count

		if total_games == 0:
			win_rate = 0
		else:
			win_rate = int(entry.correct_count / total_games * 100)

		e = discord.Embed()

		e.set_author(name=member.display_name, icon_url=member.avatar_url)

		e.add_field(name='Score', value=str(entry.score))
		e.add_field(name='Correct', value='{} games'.format(str(entry.correct_count)))
		e.add_field(name='Wrong', value='{} games'.format(str(entry.wrong_count)))
		e.add_field(name='Games played', value='{} games'.format(str(total_games)))
		e.add_field(name='Success rate', value='{}%'.format(str(win_rate)))

		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Trivia(bot))
