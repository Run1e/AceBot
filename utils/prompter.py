import discord
import asyncio

from discord.ext import commands

YES_EMOJI = '\N{WHITE HEAVY CHECK MARK}'
NO_EMOJI = '\N{CROSS MARK}'


async def prompter(ctx, title=None, prompt=None):
	'''Creates a yes/no prompt.'''

	#if ctx.author.id == ctx.bot.owner_id:
	#	return True

	prompt = prompt or 'No description provided.'
	prompt += '\n\nPress {} to continue, {} to abort.'.format(YES_EMOJI, NO_EMOJI)

	e = discord.Embed(
		description=prompt
	)

	e.set_author(name=title or 'Prompter', icon_url=ctx.bot.user.avatar_url)

	msg = await ctx.send(embed=e)

	await msg.add_reaction(YES_EMOJI)
	await msg.add_reaction(NO_EMOJI)

	def check(reaction, user):
		return str(reaction) in (YES_EMOJI, NO_EMOJI) and user == ctx.author and reaction.message.id == msg.id

	try:
		reaction, user = await ctx.bot.wait_for('reaction_add', check=check, timeout=60.0)
		return True if str(reaction) == YES_EMOJI else False
	except asyncio.TimeoutError:
		await ctx.send('Prompt timeout.')
		return False
	finally:
		await msg.delete()


async def admin_prompter(ctx):
	res = await prompter(
		ctx, title='Warning!',
		prompt=(
			'You are about to do an administrative action on an item you do not own.\n\n'
			'Are you sure you want to continue?'
		)
	)

	if res is False:
		raise commands.CommandError('Administrative action aborted.')

	return True

