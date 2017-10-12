import discord
from discord.ext import commands

bot = commands.Bot(command_prefix='!', description='Bot made by RUNIE')

extensions = (
	'cogs.commands.commands'
	, 'cogs.autohotkey.autohotkey'
)

@bot.event
async def on_ready():
	await bot.change_presence(game=discord.Game(name='autohotkey.com', type=1, url='http://autohotkey.com/'))

	if __name__ == '__main__':
		print(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
		for extension in extensions:
			bot.load_extension(extension)
	print(f'Successfully connected!')

with open('lib/bot_token.txt', 'r') as f:
	bot.run(f.read())