import re
from bs4 import BeautifulSoup

from utils.string_manip import html2markdown, find_nth


class BaseHandler:
	url_base = None
	file_base = None

	def __init__(self, path, handler):
		self.file = path
		self.handler = handler

		with open(self.file_base + '/' + path, 'r') as f:
			self.bs = BeautifulSoup(f.read(), 'html.parser')

	@property
	def url(self):
		return f'{self.url_base}/{self.file}'

	async def parse(self):
		await self.handler([self.get_name()], self.file, self.get_desc())

	def get_name(self):
		h1 = self.bs.find('h1')

		if h1 is None:
			return None

		for span in h1.find_all('span'):
			span.decompose()

		return h1.text.strip()

	def get_desc(self):
		p = self.bs.find('p')

		if p is None:
			return None

		return self.pretty_desc(p)

	def pretty_desc(self, desc):
		md = html2markdown(str(desc), self.url)

		sp = md.split('.\n')
		return md[0:len(sp[0]) + 1] if len(sp) > 1 else md


class SimpleHandler(BaseHandler):
	def get_desc(self):
		meta_desc = self.bs.find('meta', attrs=dict(name='description', content=True))
		if meta_desc is None:
			return None
		return meta_desc['content']

	async def parse(self):

		proper_name = self.get_name()
		if proper_name is None:
			return

		desc = self.get_desc()
		if desc is None:
			return

		name = ''
		for sect in re.split('([a-z][A-Z])', self.file.replace('_', ' ').split('.')[0]):
			if re.match('^[a-z][A-Z]$', sect):
				name += sect[0] + ' ' + sect[1]
			else:
				name += sect

		# ew, but whatever
		if name == 'Auto Hotkey':
			name = 'AutoHotkey'

		names = [name, proper_name]

		await self.handler(
			names,
			self.file,
			desc
		)


class CommandsHandler(BaseHandler):
	async def parse(self):
		await self.handler(
			self.get_names(),
			self.file,
			self.get_desc(),
			self.get_syntax(),
			self.get_params()
		)

	def transform_names(self, names):
		new_names = []

		for name in names:
			mtch = re.search('\[(.*)\]', name)

			if mtch is None:
				new_names.append(name)
				continue

			extra = mtch.group(1)
			with_extra = name.replace('[', '').replace(']', '')
			without_extra = name.replace(f'[{extra}]', '').replace('  ', ' ')  # last replace is kinda hacky

			new_names.extend((without_extra, with_extra))

		return new_names

	def get_names(self):
		name = self.get_name()

		split = name.split(' / ')

		for idx, part in enumerate(split):
			split[idx] = part.strip()

		split = self.transform_names(split)

		return split

	def get_syntax(self):
		syntax = self.bs.find('pre', class_='Syntax')

		if syntax is None:
			return None

		for span in syntax.find_all('span', class_='optional'):
			span.replace_with(f'[{span.text}]')

		return str(syntax.text)

	def get_params(self):
		dl = self.bs.find('dl')

		if dl is None:
			return None

		params = dict()

		for dt, dd in zip(dl.find_all('dt'), dl.find_all('dd')):
			params[', '.join(text.strip() for text in dt.text.split('\n'))] = dd.text

		if not len(params):
			return None

		return params


class CommandListHandler(BaseHandler):
	async def parse(self):
		for tag in self.bs.find_all('h3', id=True):
			for span in tag.find_all('span'):
				span.decompose()

			name = tag.text.strip()
			desc = tag.next_element.next_element.next_element
			syntax = self.bs.find('span', class_='func', string=name)

			if syntax is not None:
				syntax = syntax.parent

				for span in syntax.find_all('span', class_='optional'):
					span.replace_with(f'[{span.text}]')

				syntax = str(syntax.text)

			await self.handler([name], f'{self.file}#{name}', self.pretty_desc(desc), syntax)


class VariablesHandler(BaseHandler):
	async def parse(self):
		for tag in self.bs.find_all('tr', id=True):
			names = []
			for idx, td in enumerate(tag.find_all('td')):
				if idx == 0:
					for span in tag.td.find_all('span', class_='ver'):
						span.decompose()

					for name in [text.strip() for text in td.text.split('\n')]:
						if not len(name):
							continue
						for name in name.split(', '):
							for name in name.split(' '):
								names.append(name)

				elif idx == 1:
					desc = self.pretty_desc(td)
				else:
					break

			# if the id has some other searchable data that
			# isn't just the var name without the A_ we add it
			tag_id = tag['id']
			if f'A_{tag_id}' not in names and tag_id not in names:
				names.append(tag['id'])

			await self.handler(names, f"{self.file}#{tag['id']}", desc)
