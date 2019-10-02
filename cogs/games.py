import discord
import asyncio
import string

from discord.ext import commands
from datetime import datetime
from urllib.parse import unquote
from random import randrange, choice, sample
from enum import Enum

from cogs.mixins import AceMixin
from utils.configtable import ConfigTable


# TRIVIA CONSTANTS

class Difficulty(Enum):
	EASY = 1
	MEDIUM = 2
	HARD = 3


CORRECT_EMOJI = '\N{WHITE HEAVY CHECK MARK}'
WRONG_EMOJI = '\N{CROSS MARK}'

CORRECT_MESSAGES = (
	'Nice one!',
	'That\'s right!',
	'That one was easy, eh?',
	'Correct!',
)

WRONG_MESSAGES = (
	'Nope!',
	'Oof.',
	'Yikes.',
	'That one was hard.',
	'That was wrong!',
	'That wasn\'t easy.',
	'Afraid that\'s wrong!',
	'That\'s incorrect!',
)


DIFFICULTY_COLORS = {
	Difficulty.EASY: discord.Color.blue(),
	Difficulty.MEDIUM: discord.Color.from_rgb(212, 212, 35),
	Difficulty.HARD: discord.Color.red()
}

API_URL = 'https://opentdb.com/api.php'
QUESTION_TIMEOUT = 20.0

MULTIPLE_MAP = {
	('1', 'one'): '1️⃣',
	('2', 'two'): '2️⃣',
	('3', 'three'): '3️⃣',
	('4', 'four'): '4️⃣'
}

BOOLEAN_MAP = {
	('y', 'yes', 't', 'true', '1'): '\N{REGIONAL INDICATOR SYMBOL LETTER Y}',
	('n', 'no', 'f', 'false', '0', '2'): '\N{REGIONAL INDICATOR SYMBOL LETTER N}'
}

SCORE_POT = {
	Difficulty.EASY: 400,
	Difficulty.MEDIUM: 800,
	Difficulty.HARD: 1200
}

PENALTY_DIV = 2

# NATO CONSTANTS

PHONETICS = (
	('alpha', 'alfa'), 'bravo', 'charlie', 'delta', 'echo', 'foxtrot', 'golf', 'hotel', 'india', ('juliet', 'juliett'),
	'kilo', 'lima', 'mike', 'november', 'oscar', 'papa', 'quebec', 'romeo', 'sierra', 'tango', 'uniform', 'victor',
	('whiskey', 'whisky'), ('x-ray', 'xray'), 'yankee', 'zulu'
)

LETTERS = list(string.ascii_lowercase)
NATO = {x[0]: x[1] for x in zip(LETTERS, PHONETICS)}


class DifficultyConverter(commands.Converter):
	async def convert(self, ctx, argument):
		name = argument.upper()

		try:
			return Difficulty[name]
		except KeyError:
			pass

		try:
			return Difficulty(int(name))
		except ValueError:
			raise commands.CommandError('\'{}\' is not a valid difficulty.'.format(argument.lower()))


class Games(AceMixin, commands.Cog):
	def __init__(self, bot):
		super().__init__(bot)

		self.config = ConfigTable(bot, 'trivia', ('guild_id', 'user_id'))
		self.playing = set()

	def _create_key(self, ctx):
		return (ctx.guild.id, ctx.author.id)

	def set_playing(self, ctx):
		key = self._create_key(ctx)

		if key not in self.playing:
			self.playing.add(key)

	def unset_playing(self, ctx):
		key = self._create_key(ctx)

		if key in self.playing:
			self.playing.remove(key)

	def is_playing(self, ctx):
		return self._create_key(ctx) in self.playing

	@commands.group(invoke_without_command=True)
	@commands.bot_has_permissions(embed_links=True, add_reactions=True)
	@commands.cooldown(rate=1, per=300.0, commands.BucketType.member)
	async def trivia(self, ctx, *, difficulty: DifficultyConverter = None):
		'''Trivia time! Optionally specify a difficulty as argument. Valid difficulties are `easy`, `medium` and `hard`.'''

		if self.is_playing(ctx):
			return

		self.set_playing(ctx)

		diff = difficulty

		if diff is None:
			diff = choice(list(Difficulty))

		params = dict(
			amount=1,
			encode='url3986',
			difficulty=diff.name.lower(),
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
		elif question_type == 'boolean':
			options = ('True', 'False')
			correct_pos = int(correct_answer == 'False')
		else:
			raise ValueError('Unknown question type: {}'.format(question_type))

		option_reference = BOOLEAN_MAP if question_type == 'boolean' else MULTIPLE_MAP

		question_string = '{}\n\n{}\n'.format(
			question,
			'\n'.join('{} {}'.format(emoji, option) for emoji, option in zip(option_reference.values(), options))
		)

		e = discord.Embed(
			title='Trivia time!',
			description='**Category**: {}\n**Difficulty**: {}'.format(category, diff.name.lower()),
			color=DIFFICULTY_COLORS[diff]
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
						answered_at = datetime.utcnow()

						score = self._calculate_score(SCORE_POT[diff], answered_at - now)

						if idx == correct_pos:
							current_score = await self._on_correct(ctx, answered_at, question_hash, score)

							e = discord.Embed(
								title='{}  {}'.format(CORRECT_EMOJI, choice(CORRECT_MESSAGES)),
								description='You gained {} points.'.format(score),
								color=discord.Color.green()
							)

							e.set_footer(text='Score: {}'.format(current_score))
							await ctx.send(embed=e)
						else:
							score = int(score / PENALTY_DIV)
							current_score = await self._on_wrong(ctx, answered_at, question_hash, score)

							e = discord.Embed(
								title='{}  {}'.format(WRONG_EMOJI, choice(WRONG_MESSAGES)),
								description='You lost {} points.'.format(score),
								color=discord.Color.red()
							)

							e.set_footer(text='Score: {}'.format(current_score))

							if question_type == 'multiple':
								e.description += '\nThe correct answer is ***`{}`***'.format(correct_answer)

							await ctx.send(embed=e)

						return

			except asyncio.TimeoutError:
				score = int(SCORE_POT[diff] / 4)

				await ctx.send('Question timed out and you lost {} points. Answer within {} seconds next time!'.format(
						score, int(QUESTION_TIMEOUT)
				))

				await self._on_wrong(ctx, question_hash, score)
				return

	def _calculate_score(self, pot, time_spent):
		return int(pot * (QUESTION_TIMEOUT - time_spent.total_seconds() / 2) / QUESTION_TIMEOUT)

	async def _on_correct(self, ctx, answered_at, question_hash, add_score):
		entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

		await entry.update(score=entry.score + add_score, correct_count=entry.correct_count + 1)
		await self._insert_question(ctx, answered_at, question_hash, True)

		self.unset_playing(ctx)
		return entry.score

	async def _on_wrong(self, ctx, answered_at, question_hash, remove_score):
		entry = await self.config.get_entry(ctx.guild.id, ctx.author.id)

		await entry.update(score=entry.score - remove_score, wrong_count=entry.wrong_count + 1)
		await self._insert_question(ctx, answered_at, question_hash, False)

		self.unset_playing(ctx)
		return entry.score

	async def _insert_question(self, ctx, answered_at, question_hash, result):
		await self.db.execute(
			'INSERT INTO trivia_stats (guild_id, user_id, timestamp, question_hash, result) VALUES ($1, $2, $3, $4, $5)',
			ctx.guild.id, ctx.author.id, answered_at, question_hash, result
		)

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
		e.add_field(name='Correct percentage', value='{}%'.format(str(win_rate)))

		await ctx.send(embed=e)

	@commands.command()
	async def nato(self, ctx, count: int = 3):
		'''Learn the NATO phonetic alphabet.'''

		if count < 1:
			raise commands.CommandError('Please pick a length larger than 0.')

		if count > 16:
			raise commands.CommandError('Sorry, please pick lengths lower or equal to 16.')

		lets = sample(LETTERS, k=count)

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
				asd = NATO[let]
				right.append(asd[0] if isinstance(asd, tuple) else asd)
			await ctx.send(f'Sorry, that was wrong! The correct answer was `{" ".join(right).upper()}`')

		for index, part in enumerate(answer):
			answer = NATO[lets[index]]
			if isinstance(answer, tuple):
				if part not in answer:
					return await failed()
			else:
				if part != answer:
					return await failed()

		await ctx.send('Correct! ✅')


def setup(bot):
	bot.add_cog(Games(bot))
