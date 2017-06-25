import settings
import commands
import discord
from funcs import *
import re
import json
from urllib import parse
from fuzzywuzzy import fuzz, process

def help(message):
	file = open("help.txt", "r")
	help = file.read()
	file.close()
	return help

def highlight(message):
	return "```AutoHotkey\n{}\n```*Paste by {}*".format(message.content[message.content.find(' ') + 1:], message.author.mention)

def update(message):
	site = httpget('https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')
	version = json.loads(site)['tag_name']
	down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])
	return {"embed": discord.Embed(title="<:ahk:317997636856709130> AutoHotkey_L", description="Latest version: {}".format(version), url=down)}

def vibrancer(message):
	site = httpget('https://api.github.com/repos/Run1e/Vibrancer/releases/latest')
	version = json.loads(site)['tag_name']
	return {"embed": discord.Embed(title="Vibrancer for NVIDIA", description="Latest version: {}".format(version), url="http://vibrancer.com/")}

def forumasd(message):
	return 'Not yet.'
	search = message.content[7:]
	site = httpget("https://duckduckgo.com/html/?q={}".format(search))
	print(site)
	return

def docs(message, cmd=''):
	res = ''

	if cmd == '':
		cmd = message.content[message.content.find(' ') + 1:]

	for x in settings.docs:
		if cmd.lower() == x.lower():
			res = x
			break
		elif x.startswith(cmd + ' '):
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
	desc = settings.docs_assoc[res].get('desc', '')
	url = settings.docs_assoc[res].get('dir', '')

	if not len(title):
		title = res

	em = {"title": title, "description": desc}

	if len(url):
		em['url'] = "https://autohotkey.com/docs/{}".format(url)

	return {"embed": discord.Embed(**em)}

def studio(message):
	site = Request('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')
	site = urlopen(site).read().decode('utf8')
	version = site.split('\r\n')[0]
	return {"embed": discord.Embed(title='<:studio:317999706087227393> AHK Studio', description='Latest version: ' + version, url='https://autohotkey.com/boards/viewtopic.php?f=62&t=300')}