import html
import re
import settings
import requests
import json
from bs4 import BeautifulSoup

def findnth(haystack, needle, n):
	parts= haystack.split(needle, n+1)
	if len(parts)<=n+1:
		return -1
	return len(haystack)-len(parts[-1])-len(needle)

def limit_text(text, max_char, max_lines):
	type = 0
	if text.count('\n') > max_lines:
		type = 1
		text = text[:findnth(text, '\n', max_lines)]
	if len(text) > max_char:
		text = text[:max_char]
		type = 2
	if type == 1:
		text = text + '\n...'
	elif type == 2:
		text = text + '...'
	return text

def forumsnippet(link):
	if link.find('#'):
		print(link)
		link = re.sub('\#p\d*', '', link)
		print(link)
	link = re.sub('&start=\d*', '', link)

	req = requests.get(link)

	soup = BeautifulSoup(req.text, 'html.parser')

	# .replace(" - AutoHotkey Community", '')

	title = soup.find('title').text
	title = title.replace(" - AutoHotkey Community", '')

	cont = str(req.text).split('<div class="content">')[1].split('</div>')[0]
	cont = cont.replace("<br/>", "\n")
	cleancont = re.sub(re.compile('<.*?>'), '', cont)
	cleancont = re.sub("\n\n+", "\n\n", cleancont)
	cleancont = limit_text(cleancont, settings.forum_char, settings.forum_line)
	cleancont = html.unescape(cleancont)

	return {"title": title, "description": cleancont, "url": link}

def pastesnippet(link):
	link = link.replace("?p=", "?r=")
	link = link.replace("?e=", "?r=")

	req = requests.get(link)
	flen = len(req.text)
	site = limit_text(req.text, settings.ahk_char, settings.ahk_line)

	if len(site) == flen:
		return "```AutoHotkey\n{}```".format(site)
	else:
		return ''