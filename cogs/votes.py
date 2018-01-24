import discord
from discord.ext import commands

import asyncio

class Votes:
	def __init__(self, bot):
		self.bot = bot
		self.votes = {}
		self.time = 50

	async def on_reaction_add(self, reaction, user):
		if user == self.bot.user or reaction.message.channel not in self.votes.keys():
			return

		if reaction.emoji not in self.votes[reaction.message.channel]['score']:
			await reaction.message.remove_reaction(reaction.emoji, user)

		for emoji, users in self.votes[reaction.message.channel]['score'].items():
			if user in users:
				await reaction.message.remove_reaction(emoji, user)
			if reaction.emoji == emoji:
				self.votes[reaction.message.channel]['score'][emoji].append(user)

	async def on_reaction_remove(self, reaction, user):
		if user == self.bot.user or reaction.message.channel not in self.votes.keys():
			return

		for emoji, users in self.votes[reaction.message.channel]['score'].items():
			if reaction.emoji == emoji:
				self.votes[reaction.message.channel]['score'][emoji].remove(user)

	@commands.command()
	async def vote(self, ctx, question: str, *choices):
		"""Let people in the channel vote on a question!"""
		if len(choices) > 9:
			return await ctx.send('Too many choices!')
		if len(choices) < 2:
			return await ctx.send('Too few choices!')
		if ctx.channel in self.votes.keys():
			return await ctx.send('Vote already in progress!')

		self.votes[ctx.channel] = {'score': {}}

		await ctx.message.delete()

		msg_content = f'{ctx.message.author.mention} has just started a vote!\n\n***{question}***\n\n'

		for i, choice in enumerate(choices):
			msg_content += f'{i + 1}\u20e3 - *{choice}*\n'
			self.votes[ctx.channel]['score'][f'{i + 1}\u20e3'] = []

		msg_content += f'\nVote ends in {self.time} seconds. Vote with reactions below!'

		msg = await ctx.send(msg_content)

		for emoji in self.votes[ctx.channel]['score'].keys():
			try:
				await msg.add_reaction(emoji)
			except discord.errors.Forbidden:
				self.votes.pop(ctx.channel)
				return await msg.edit(content="`Missing permissions, can't add emojis.`")

		self.votes[ctx.channel]['msg'] = msg

		await asyncio.sleep(self.time)

		max = 0
		i = 0
		winners = []

		for emoji, users in self.votes[ctx.channel]['score'].items():
			if len(users) > max:
				max = len(users)

		if not max == 0:
			for emoji, users in self.votes[ctx.channel]['score'].items():
				if len(users) == max:
					winners.append(choices[i])
				i += 1

		self.votes.pop(ctx.channel)
		await msg.delete()

		text = f'{ctx.message.author.mention} asked:\n\n***{question}***\n\n'

		max_text = f"**{max}** {'person' if max == 1 else 'people'}"

		if len(winners) == 0:
			text += 'And no one voted...'
		elif len(winners) == 1:
			text += f'And {max_text} answered with:\n'
		else:
			text += f'And at **{max}** votes each, there was a tie:\n'

		for choice in winners:
			text += f'\n***{choice}***'

		await ctx.send(text)

def setup(bot):
	bot.add_cog(Votes(bot))