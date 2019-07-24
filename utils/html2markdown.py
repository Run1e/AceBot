import discord.utils
from bs4 import BeautifulSoup, NavigableString


class CodeTagHandler:
	def __init__(self, big_box=False, language=None):
		self.big_box = big_box
		self.language = None if big_box is False else language or None
		self._nl = '\n' if big_box else ''

	def convert(self, tag, content, credit):
		if self.big_box:
			content = content.replace('```', '`\u200b``')
		return (self.language or '') + self._nl + content + self._nl


class UrlTagHandler:
	def __init__(self, url=None, escaper=None):
		self.url = url
		self.escaper = escaper

	def convert(self, tag, content, credit):
		if self.url is None:
			return content

		href = tag['href']

		if href.startswith('#'):
			use_url = self.url + href
		elif href.startswith(('http', 'ftp')):
			use_url = href
		else:
			use_url = '/'.join(self.url.split('/')[:-1]) + '/' + href

		fmt = '[{}]({})'

		text = discord.utils.escape_markdown(tag.string)
		full = fmt.format(text, use_url)

		greedy_chars = 3

		if credit > len(full):
			return full
		elif credit >= len(use_url) + 4 + greedy_chars:
			return fmt.format(text[0:credit - len(use_url) - 4], use_url)
		else:
			return text[0:credit]


class MaxLengthReached(Exception):
	def __init__(self, message=None):
		self.message = message


def html2markdown(html, escaper=None, url=None, big_box=False, language=None, parser='html.parser', max_length=None):
	'''Converts html to markdown.'''

	if max_length is not None:
		if max_length < 1 or not isinstance(max_length, int):
			raise ValueError('max_length should be above 0 and integer type.')

	if language is not None and big_box is False:
		raise ValueError('Cannot have code box language with small boxes. Set big_box=True')

	if not callable(escaper):
		raise ValueError('No callable escaper set. use \'discord.utils.escape_markdown\' if using discord.py')

	# tags that only prepends something
	prepend = dict(
		br='\n',  	# linebreak
		p='\n\n',  	# paragraph
	)

	# tags that wrap the contents in the same character
	wrap = dict(
		b='**',  	# bold
		em='*',  	# emphasis
		i='*',  	# italics
		div='\n',  	# div
		code='```' if big_box else '`'
	)

	# tags that wrap the contents in two different characters
	multiwrap = dict(
		ul=('\n\n', '\n'),	# starts a list section
		li=(' - ', '\n')  	# list item
	)

	specials = dict(
		a=UrlTagHandler(url, escaper),
		code=CodeTagHandler(big_box, language)
	)

	def get_wrapper(name):
		if name in prepend:
			front = prepend[name]
			back = ''
		elif name in wrap:
			front = wrap[name]
			back = front
		elif name in multiwrap:
			front = multiwrap[name][0]
			back = multiwrap[name][1]
		else:
			front, back = '', ''

		return front, back

	bs = BeautifulSoup(html, parser)

	def traverse(tag, credit):
		result = ''

		for entry in tag.contents:
			if isinstance(entry, NavigableString):
				if entry == '\n':
					continue

				if tag.name in specials:
					to_add = specials[tag.name].convert(tag, entry, credit)
					if len(to_add) > credit:
						raise MaxLengthReached()
				else:
					to_add = escaper(entry)
					if len(to_add) > credit:
						raise MaxLengthReached(result + to_add[0:credit])

				result += to_add
				credit -= len(to_add)
			else:
				front, back = get_wrapper(entry.name)

				if credit <= len(front + back):
					raise MaxLengthReached(result)

				result += front
				credit -= len(front + back)

				try:
					to_add, credit = traverse(entry, credit)
				except MaxLengthReached as exc:
					if exc.message is None:
						raise MaxLengthReached(result if not len(front) else result[:len(front) * -1])
					else:
						raise MaxLengthReached(result + exc.message + back)

				result += to_add + back

		return result, credit


	try:
		r, c = traverse(bs, max_length - 3)
	except MaxLengthReached as exc:
		r = exc.message.strip() + '...'

	return r.strip()