import discord
import re

from funcs import *
import settings
import commands

client = discord.Client()

@client.event
async def on_message(message):
	if message.author == client.user:
		return

	# ignore from chan
	if message.channel.name in settings.ignore_chan:
		return

	msg = ''

	if message.content.startswith('!'):
		cmd = message.content[1:].split(' ')[0]
		param = message.content[2 + len(cmd):].split(' ')

		if cmd in settings.ignore_cmd:
			return

		if cmd in settings.commands:
			msg = commands.commands(message, cmd)
		elif cmd in settings.embeds:
			msg = commands.embeds(message, cmd)
		elif hasattr(commands, cmd):
			msg = getattr(commands, cmd)(message, param)
		else:
			msg = commands.docs(cmd)

		if cmd in settings.del_cmd:
			await client.delete_message(message)

	else:
		try:
			link = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content)[0]
		except Exception:
			link = ''

		if link.startswith("http://p.ahkscript.org/?"):
			msg = pastesnippet(link)
		elif link.startswith("https://autohotkey.com/boards/viewtopic.php?"):
			msg = forumsnippet(link)

	if msg != '':
		printtime()
		print("{} in {}: {}".format(message.author, message.channel, message.content.split("\n")[0]))
		if type(msg) is dict:
			to_dict = msg['embed'].to_dict()
			print(to_dict['title'])
			print(to_dict['description'])
			await client.send_message(message.channel, **msg)
		else:
			print(msg.split('\n')[0])
			await client.send_message(message.channel, msg)

	return

@client.event
async def on_ready():
	print(client.user.name)
	print(client.user.id)
	print(discord.__version__)
	await client.change_presence(game=discord.Game(name='autohotkey.com'))

file = open("token.txt", "r")
token = file.read()
file.close()
client.run(token)
