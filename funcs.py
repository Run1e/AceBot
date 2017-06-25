import html
import re
import datetime
import settings
from urllib.request import Request, urlopen

def httpget(url):
	site = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
	return urlopen(site).read().decode('utf8')

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
	import discord
	site = httpget(link)

	title = str(site).split('<title>')[1].split('</title>')[0]
	title = title.replace(" - AutoHotkey Community", '')
	author = str(site).split('class=\"username\">')[1].split('</a>')[0]

	cont = str(site).split('<div class="content">')[1].split('</div>')[0]
	cont = cont.replace("<br/>", "\n")
	cleancont = re.sub(re.compile('<.*?>'), '', cont)
	cleancont = re.sub("\n\n+", "\n\n", cleancont)

	cleancont = limit_text(cleancont, settings.forum_char, settings.forum_line)

	# escaping last since it was messing with len(). it might result in a cut-off html code but whatever it's good enough
	cleancont = html.unescape(cleancont)

	return {"embed": discord.Embed(title="{} - thread by {}".format(title, author), description=cleancont, url=link)}

def pastesnippet(link):
	link = link.replace("?p=", "?r=")
	link = link.replace("?e=", "?r=")

	site = httpget(link)
	flen = len(site)
	site = limit_text(site, settings.ahk_char, settings.ahk_line)

	if len(site) == flen:
		return "```AutoHotkey\n{}```".format(site)
	else:
		return ''