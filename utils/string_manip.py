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


def html2markdown(html, url='', big_box=False, language=None, parser='html.parser'):

	prepend = {'br': '\n', 'li': '\u200b\t- ', 'ul': '\n'}
	wrap = {'b': '**', 'em': '*', 'i': '*', 'div': '\n'}

	# replace all text (not tags) with stripped markdown versions
	res = re.finditer(r'>((\s|.)*?)<', str(html))
	plain = html

	new = ''
	prev = 0
	for m in res:
		start, stop = m.span()
		stripped = strip_markdown(plain[start + 1:stop - 1])
		new += plain[prev:start + 1] + stripped
		prev = stop - 1

	# create a bs4 instance of the html
	bs = BeautifulSoup(new, parser)

	for key, value in wrap.items():
		for tag in reversed(bs.find_all(key, recursive=True)):
			tag.replace_with(value + tag.text + value)

	code_wrap = '```' if big_box else '`'
	for tag in reversed(bs.find_all('code', recursive=True)):
		tag.replace_with(f"{code_wrap}{'' if language is None or not big_box else language}\n{tag.text}\n{code_wrap}")

	for key, value in prepend.items():
		for tag in reversed(bs.find_all(key, recursive=True)):
			tag.replace_with(value + tag.text)

	if len(url) and not url.endswith('/'):
		url += '/'

	# replace hyperlinks with markdown hyperlinks
	for a in bs.find_all('a', href=True, recursive=True):
		href = a["href"]
		if href.startswith('../'):
			href = href[3:]
		a.replace_with(f'[{a.text}]({url}{href})')

	return str(bs.text)


def shorten(text, max_char, max_newline):
	shortened = False

	if len(text) > max_char:
		text = text[0:max_char]
		shortened = True

	if text.count('\n') > max_newline:
		text = text[0:find_nth(text, '\n', max_newline)]
		shortened = True

	if shortened:
		text = text[0:len(text) - 3] + '...'

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
		'user': user.mention,
		'member_count': guild.member_count
	}

	for key, val in repl.items():
		string = string.replace('{' + key + '}', str(val))

	return string
