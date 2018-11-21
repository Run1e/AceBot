import discord
from discord.ext import commands

import asyncio

from cogs.base import TogglableCogMixin

class Highlighter(TogglableCogMixin):
	
	timeout = 2
	emoji = '\U0000274C'
	
	async def __local_check(self, ctx):
		return await self._is_used(ctx)
	
	@commands.command(aliases=['h1'])
	@commands.bot_has_permissions(manage_messages=True, add_reactions=True)
	async def hl(self, ctx, *, code):
		'''Highlight some code.'''
		
		code = ctx.message.clean_content[4:]
		
		await ctx.message.delete()
		
		msg = await ctx.send(f'```autoit\n{code}```Paste by {ctx.author.mention} - Click the {self.emoji} within {self.timeout} minutes to remove.')
		
		await msg.add_reaction('\U0000274C')
		
		async def on_reaction_add(reaction, user):
			if reaction.message.id != msg.id or user.bot:
				return
			if reaction.emoji == self.emoji and (user is ctx.author or user.permissions_in(reaction.message.channel).manage_messages):
				await msg.delete()
			else:
				await reaction.message.remove_reaction(reaction, user)
			
		self.bot.add_listener(on_reaction_add)
		await asyncio.sleep(self.timeout * 60)
		self.bot.remove_listener(on_reaction_add)
		
		try:
			await msg.clear_reactions()
			await msg.edit(content=' - '.join(msg.content.split(' - ')[:-1]))
		except discord.errors.NotFound:
			pass # message already deleted
		
	@commands.command(aliases=['p'], hidden=True)
	async def paste(self, ctx):
		msg = 'To paste code snippets directly into the chat, use the highlight command:\n```.hl *paste code here*```'
		if (ctx.guild.id == 115993023636176902):
			msg += 'If you have a larger script you want to share, paste it to the AutoHotkey pastebin instead:\nhttp://p.ahkscript.org/'
		await ctx.send(msg)
			
	
def setup(bot):
	bot.add_cog(Highlighter(bot))