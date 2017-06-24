import settings
from funcs import *
import re
import json
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

def highlight(message, param):
	return "```AutoHotkey\n{}\n```*Paste by {}*".format(" ".join(param), message.author.mention)

def update(message, param):
	import discord
	site = httpget('https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')

	version = json.loads(site)['tag_name']
	down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])

	return {"embed": discord.Embed(title="<:ahk:317997636856709130> AutoHotkey_L", description="Latest version: {}".format(version), url=down)}

def docs(cmd):
	import discord
	res = ''

	for x in settings.docs:
		if cmd.lower() == x.lower():
			res = x
			break

	if not len(res):
		for x in process.extract(cmd, settings.docs, scorer=fuzz.partial_ratio, limit=999999):
			if not len(res):
				res = x[0]
			if x[0].lower().startswith(cmd):
				res = x[0]
				break
			if cmd.upper() == ''.join([c for c in x[0] if c.isupper()]):
				res = x[0]
				break

	title = settings.docs_assoc[res].get('syntax', '')
	if not len(title):
		title = res

	return {"embed": discord.Embed(title=title, description=settings.docs_assoc[res]['desc'], url="https://autohotkey.com/docs/{}".format(settings.docs_assoc[res]['dir']))}

def studio(message, param):
	import discord
	site = Request('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')
	site = urlopen(site).read().decode('utf8')
	version = site.split('\r\n')[0]
	return {"embed": discord.Embed(title='<:studio:317999706087227393> AHK Studio', description='Latest version: ' + version, url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300')}

def commands(message, cmd):
	return settings.commands[cmd].format(message)

def embeds(message, cmd):
		import discord
		em = {}
		for x in ['title', 'description', 'url']:
			if x in settings.embeds[cmd]:
				em[x] = settings.embeds[cmd][x].format(message)
		return {"embed": discord.Embed(**em)}


def ahk(message, param):
	return update(message, param)
def version(message, param):
	return update(message, param)
def hl(message, param):
	return highlight(message, param)