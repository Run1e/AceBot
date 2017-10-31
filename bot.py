import discord
from discord.ext import commands

bot = commands.Bot(command_prefix=('!', '.'), description='Bot made by RUNIE')

extensions = (
	'cogs.commands',
	'cogs.autohotkey',
	'cogs.admin'
)

@bot.event
async def on_ready():
	await bot.change_presence(game=discord.Game(name='autohotkey.com', type=1, url='http://autohotkey.com/'))

	# list of users to ignore (like for example bots or people misusing the bot)
	bot.ignore_users = (
		327874898284380161,
		155149108183695360,
		159985870458322944
	)

	if __name__ == '__main__':
		print(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')
		for extension in extensions:
			bot.load_extension(extension)
	print(f'Successfully connected!')

@bot.before_invoke
async def before_any_command(ctx):
	print(f'----------------\nServer: {ctx.guild.name}\nUser: {ctx.message.author.name}\nCommand: {ctx.command.name}\n')
	for x in ctx.kwargs:
		print(x + ": " + ctx.kwargs[x].split('\n')[0])


# overwrite discord.Embed with a monkey patched class that automatically sets the color attribute
class Embed(discord.Embed):
    def __init__(self, color=0x78A064, **attrs):
        attrs['color'] = color
        super().__init__(**attrs)

discord.Embed = Embed

with open('lib/bot_token.txt', 'r') as f:
	bot.run(f.read())