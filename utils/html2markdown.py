import re
import discord.utils
from bs4 import BeautifulSoup

def html2markdown(html, url='', big_box=False, language=None, parser='html.parser'):

	prepend = {'br': '\n', 'li': ' - ', 'ul': '\n'}
	wrap = {'b': '**', 'em': '*', 'i': '*', 'div': '\n'}

	# replace all text (not tags) with stripped markdown versions
	res = re.finditer(r'>((\s|.)*?)<', str(html))
	plain = html

	new = ''
	prev = 0
	for m in res:
		start, stop = m.span()
		stripped = discord.utils.escape_markdown(plain[start + 1:stop - 1])
		new += plain[prev:start + 1] + stripped
		prev = stop - 1

	# create a bs4 instance of the html
	bs = BeautifulSoup(new, parser)

	for key, value in wrap.items():
		for tag in reversed(bs.find_all(key, recursive=True)):
			tag.replace_with(value + tag.text + value)

	code_wrap = '```' if big_box else '`'
	nl = '\n' if big_box else ''
	for tag in reversed(bs.find_all('code', recursive=True)):
		tag.replace_with(f"{code_wrap}{language or ''}{nl}{tag.text}{nl}{code_wrap}")

	for key, value in prepend.items():
		for tag in reversed(bs.find_all(key, recursive=True)):
			tag.replace_with(value + tag.text)

	# replace hyperlinks with markdown hyperlinks
	for a in bs.find_all('a', href=True, recursive=True):
		href = a["href"]
		if href.startswith('#'):
			use_url = url + href
		elif href.startswith(('http', 'ftp')):
			use_url = href
		else:
			use_url = '/'.join(url.split('/')[:-1]) + '/' + href
		a.replace_with(f'[{a.text}]({use_url})')

	return str(bs.text)
