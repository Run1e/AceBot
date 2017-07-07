import settings
import requests
import re
from bs4 import BeautifulSoup
import urllib.parse

import discord
from funcs import *
import re
import json
from fuzzywuzzy import fuzz, process

def help(message, cont):
	with open("help.txt", "r") as f:
		return f.read()

def highlight(message, cont):
	return "```AutoHotkey\n{}\n```*Paste by {}*".format(cont, message.author.mention)

def highlightpython(message, cont):
	return "```python\n{}\n```*Paste by {}*".format(cont, message.author.mention)

def update(message, cont):
	req = requests.get('https://api.github.com/repos/Lexikos/AutoHotkey_L/releases/latest')
	version = json.loads(req.text)['tag_name']
	down = "https://github.com/Lexikos/AutoHotkey_L/releases/download/{}/AutoHotkey_{}_setup.exe".format(version, version[1:])
	return {"title": "<:ahk:317997636856709130> AutoHotkey_L", "description": "Latest version: {}".format(version), "url": down}

def rep(message, cont):
	return ""
	reg = re.match('^(<@(\d*)>)$', cont)

	if reg:
		id = reg.group(2)
		if message.author.id != id:
			if not id in settings.kudos:
				settings.kudos[id] = 1
			else:
				settings.kudos[id] = settings.kudos[id] + 1
			open("kudos.json", "w").write(json.dumps(settings.kudos))
			return "{} now has a reputation of {}!".format(cont, settings.kudos[id])
	return

def docs(message, cont):
	res = ''

	for x in settings.docs:
		if cont.lower() == x.lower():
			res = x
			break
		elif x.startswith(cont + ' '):
			res = x
			break

	if not len(res):
		for x in process.extract(cont, settings.docs, scorer=fuzz.partial_ratio, limit=999999):
			if not len(res):
				res = x[0]
			if x[0].lower().startswith(cont):
				res = x[0]
				break
			if cont.upper() == ''.join([c for c in x[0] if c.isupper()]):
				res = x[0]
				break

	title = settings.docs_assoc[res].get('syntax', '')
	desc = settings.docs_assoc[res].get('desc', '')
	url = settings.docs_assoc[res].get('dir', '')

	if not len(title):
		title = res

	if title.find('\n'):
		title = title.split('\n')[0]

	em = {"title": title, "description": desc}

	if len(url):
		em['url'] = "https://autohotkey.com/docs/{}".format(url)

	return em

def weather(message, cont):
	req = requests.get("http://api.wunderground.com/api/{}/conditions/q/{}.json".format(settings.weatherapi, cont))
	we = json.loads(req.text)
	desc = ['***Weather***']
	try:
		desc.append(we['current_observation']['weather'])
	except:
		return "'{}' not found.".format(cont)
	desc.append('***Temperature***')
	desc.append("{} C ({} freedoms)".format(we['current_observation']['temp_c'], we['current_observation']['temp_f']))
	desc.append('***Wind***')
	desc.append(we['current_observation']['wind_string'])
	return {"title": "Weather for {}".format(we['current_observation']['display_location']['full'])
		, "description": "\n".join(desc)
		, "url": we['current_observation']['forecast_url']
		, "thumbnail": we['current_observation']['icon_url']
		, "footer": {"text": "Data provided by wunderground", "icon_url": "http://icons.wxug.com/graphics/wu2/logo_130x80.png"}}

def forum(message, query):
	return search(message, "site:autohotkey.com/boards/ {}".format(query))

def search(message, query):
	req = requests.get('http://google.com/search?safe=off&q={}'.format(query))
	soup = BeautifulSoup(req.text, 'html.parser')
	url = soup.find_all('div')
	url = [x for x in url if x.find('h3')]
	urls = []
	for index, item in enumerate(url):
		link = item.find('h3').find('a')
		href = link.get('href')

		item_url = href.split('=', 1)[1].split('&')[0]
		if not item_url.startswith('http'):
			continue

		snippets = [x.text for x in item.find_all('span') if x.text]
		if len(snippets) != 0:
			snippet = urllib.parse.unquote(snippets[0])
		else:
			snippet = ''

		name = urllib.parse.unquote(link.text)
		urls.append((urllib.parse.unquote(item_url), name, snippet))
		break
	if not urls:
		return 'No results.'
	else:
		domain = urllib.parse.urlparse(urls[0][0]).netloc
		return {"title": urls[0][1]
			, "description": urls[0][2]
			, "url": urls[0][0]
			, "footer": {"text": domain}}

def studio(message, cont):
	req = requests.get('https://raw.githubusercontent.com/maestrith/AHK-Studio/master/AHK-Studio.text')
	version = req.text.split('\r\n')[0]
	return {"title": "<:studio:317999706087227393> AHK Studio"
		, "description": "Latest version: " + version
		, "url": "https://autohotkey.com/boards/viewtopic.php?f=62&t=300"}

def vibrancer(message, cont):
	req = requests.get('https://api.github.com/repos/Run1e/Vibrancer/releases/latest')
	version = json.loads(req.text)['tag_name']
	return {"title": "Vibrancer for NVIDIA"
		, "description": "Latest version: {}".format(version)
		, "url": "http://vibrancer.com/"}