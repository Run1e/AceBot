import re
from bs4 import BeautifulSoup


def strip_markdown(content):
	transformations = {
		re.escape(c): '\\' + c for c in ('*', '`', '_', '~', '\\', '<', '|')
	}

	def replace(obj):
		return transformations.get(re.escape(obj.group(0)), '')

	pattern = re.compile('|'.join(transformations.keys()))
	return pattern.sub(replace, content)


def to_markdown(html):
	html = BeautifulSoup(html, 'html.parser')

	for thing in html.find_all('br'):
		thing.replace_with('\n' + thing.text)

	for key, val in {'code': '```', 'blockquote': ' '}.items():
		for thing in html.find_all(key):
			thing.replace_with(val + thing.text + val)

	return html.text


def shorten(text, max_char, max_newline):
	shortened = False

	if len(text) > max_char:
		text = text[0:max_char]
		shortened = True

	if text.count('\n') > max_newline:
		text = text[0:find_nth(text, '\n', max_newline)]
		shortened = True

	if shortened:
		text = text[0:len(text) - 4] + ' ...'

	return text


def find_nth(haystack, needle, n):
	start = haystack.find(needle)
	while start >= 0 and n > 1:
		start = haystack.find(needle, start + len(needle))
		n -= 1
	return start


def welcomify(user, guild, string):
	repl = {
		'guild': guild.name,
		'user': user.mention
	}

	for key, val in repl.items():
		string = string.replace('{' + key + '}', val)

	return string
