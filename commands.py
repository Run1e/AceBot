import settings
import requests
from bs4 import BeautifulSoup
import sympy
import urllib.parse

import discord
from funcs import *
import re
import json
import random
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

def fact(message, cont):
	return random.choice(settings.facts.splitlines())

def number(message, cont):
	try:
		cont = int(cont)
	except ValueError:
		return 'Please input a number.'
	req = requests.get('http://numbersapi.com/{}?notfound=floor'.format(cont))
	return req.text

def eval(message, cont):
	return str(sympy.sympify(cont))

def docs(message, search_terms):
	md_trans = str.maketrans({c: '\\'+c for c in '\\*#/()[]<>'})
	search_terms = search_terms.splitlines()

	# Finds a documentation page with fuzzy search
	def find_page(search_term):
		# Simple check
		for page_name in settings.docs:
			if (page_name.lower().startswith(search_term.lower() + ' ')
						or search_term.lower() == page_name.lower()):
				return page_name

		# String matching check
		matches = process.extract(
			search_term,
			settings.docs,
			scorer=fuzz.partial_ratio,
			limit=999999
		)

		for match, score in matches:
			if (search_term.upper() == ''.join(filter(str.isupper, match))
						or match.lower().startswith(search_term.lower())):
				return match

		return matches[0][0]

	# Find one page and put it in a normal embed
	if len(search_terms) == 1:
		page_name = find_page(search_terms[0])
		page = settings.docs_assoc[page_name]

		if 'syntax' in page:
			if page['syntax'].find('\n'):
				page['syntax'] = page['syntax'].split('\n')[0]

		return {
			'title': page.get('syntax', page_name),
			'description': page.get('desc', ''),
			'url': 'https://autohotkey.com/docs/' + page['dir']
				if 'dir' in page else None
		}

	# Find multiple pages and put them in embed fields
	seen_pages = set()
	fields = []
	for search_term in search_terms:
		page_name = find_page(search_term)

		# Filter for unique pages
		if page_name in seen_pages:
			continue

		seen_pages.add(page_name)

		# Add the page as a field in the embed
		page = settings.docs_assoc[page_name]

		if 'syntax' in page:
			if page['syntax'].find('\n'):
				page['syntax'] = page['syntax'].split('\n')[0]

		fields.append({
			'name': page.get('syntax', page_name),
			'value': page.get('desc', 'Link').translate(md_trans)
				if 'dir' not in page else
				'{0}\n[{1}](https://autohotkey.com/docs/{2})'.format(
					page.get('desc', 'Link').translate(md_trans),
					'Documentation',
					page['dir'].translate(md_trans)
				)
		})
	return {'title': None, 'fields': fields}

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
	if (message.author.id != "265644569784221696"):
		return "Feature only enabled for admins."
	req = requests.get('http://google.com/search?hl=en&safe=off&q={}'.format(query))
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