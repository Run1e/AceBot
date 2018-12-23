import discord, random
from discord.ext import commands

from sqlalchemy import and_

from .base import TogglableCogMixin
from utils.database import UserCoin

POWER = -0.82281617988
DEFAULT_AMOUNT = 100

STD_MULT = 'You hit a {}x multiplier and won {} coins!'
BROKE_STRINGS = ['You lost it all, you sell some of your child\'s belongings for 100 coins.',
 'You gambled away all of your inheritance and it left you unable to pay your mortgage, luckily you found 100 coins while crawling through the sewer.',
 'You lost the rest of your savings, you take to the streets and *earn* 100 coins the *hard* way ( ͡° ͜ʖ ͡°).',
 'After loosing the rest of your coins, you work in a sweatshop until you have earned back 100 coins.',
 'Without any coins to pay back your debts, the mafia comes and breaks your kneecaps, but you found 100 coins in a gutter, so you\'ve got that going for you.']

class Coins(TogglableCogMixin):
	'''Bet some coins!'''
	
	async def get_user(self, guild_id, user_id):
		coins = await UserCoin.query.where(
			and_(
				UserCoin.guild_id == guild_id,
				UserCoin.user_id == user_id
			)
		).gino.first()
		
		if coins is not None:
			return coins
		
		return await UserCoin.create(
			guild_id=guild_id,
			user_id=user_id,
			bets=0,
			coins=DEFAULT_AMOUNT
		)
	
	def get_mult(self, i):
		return 32 * pow(i, POWER)
	
	def fmt(self, num):
		return '{:,}'.format(num)
	
	@commands.command()
	@commands.cooldown(rate=1, per=60 * 60, type=commands.BucketType.member)
	async def bet(self, ctx, coins: int):
		'''Bet some coins.'''
		
		cn = await self.get_user(ctx.guild.id, ctx.author.id)
		
		if cn.coins == 0:
			cn.coins = DEFAULT_AMOUNT
		
		if coins < 1:
			await ctx.send('Sorry, you have to bet an amount greater than 0!')
			return
		
		if cn.coins < coins:
			await ctx.send('You don\'t have enough coins to bet that amount!')
			return
		
		res = random.randrange(100000) / 1000
		
		if res > 49:
			if cn.biggest_loss is None or coins > cn.biggest_loss:
				biggest_loss = coins
			else:
				biggest_loss = cn.biggest_loss
			
			new_balance = cn.coins - coins
			
			await cn.update(
				coins=DEFAULT_AMOUNT if new_balance == 0 else new_balance,
				bets=cn.bets + 1,
				biggest_loss=biggest_loss
			).apply()
			
			if new_balance == 0:
				await ctx.send(
					BROKE_STRINGS[random.randrange(0, len(BROKE_STRINGS))]
				)
			else:
				await ctx.send(f'Sorry, you lost {self.fmt(coins)} coins!')
			
			return
		
		if res < 0.1:
			mult = 1000.0
			fmt = '🎉🎉🎉 You hit the ultimate super duper mega-jackpot! With a multiplier of {} you won {} coins!!!'
		else:
			mult = self.get_mult(res)
			fmt = STD_MULT
		
		simple_mult = round(mult, 1)
		
		won = int(coins * (mult - 1))
		
		if won < 1:
			won = 1
		
		if cn.biggest_win is None or won > cn.biggest_win:
			biggest_win = won
		else:
			biggest_win = cn.biggest_win
		
		if cn.biggest_mult is None or simple_mult > cn.biggest_mult / 10:
			biggest_mult = int(simple_mult * 10)
		else:
			biggest_mult = cn.biggest_mult
		
		await cn.update(
			coins=cn.coins + won,
			bets=cn.bets + 1,
			biggest_win=biggest_win,
			biggest_mult=biggest_mult
		).apply()
		
		await ctx.send(fmt.format(simple_mult, self.fmt(won)))
	
	@commands.command()
	async def coins(self, ctx, member: discord.Member = None):
		'''Get coin stats of yourself or someone else.'''
		
		member = member or ctx.author
		
		cn = await self.get_user(ctx.guild.id, member.id)
		
		e = discord.Embed()
		
		e.set_author(name=member.name + ' Coins Stats', icon_url=member.avatar_url)
		
		e.add_field(name='Coins', value='{} coins'.format(self.fmt(cn.coins)))
		e.add_field(name='Total bets', value='{} bets'.format(cn.bets))
		
		if cn.biggest_mult is not None:
			e.add_field(name='Biggest multiplier', value='{}x'.format(cn.biggest_mult / 10))
		
		if cn.biggest_win is not None:
			e.add_field(name='Biggest win', value='{} coins'.format(self.fmt(cn.biggest_win)))
		
		if cn.biggest_loss is not None:
			e.add_field(name='Biggest loss', value='{} coins'.format(self.fmt(cn.biggest_loss)))
		
		await ctx.send(embed=e)


def setup(bot):
	bot.add_cog(Coins(bot))
