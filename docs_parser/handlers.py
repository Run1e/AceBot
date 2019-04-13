import re

from utils.string_manip import html2markdown


class BaseHandler:
	url = None

	def __init__(self, bs, path, handler):
		self.file = path
		self.handler = handler
		self.bs = bs

	def get_desc(self):
		p = self.bs.find('p')

		if p is None:
			return None

		return self.pretty_desc(p)

	def pretty_desc(self, desc):
		return html2markdown(str(desc), self.url)


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
			without_extra = name.replace(f'[{extra}]', '')

			new_names.extend((without_extra, with_extra))

		return new_names

	def get_names(self):
		tag = self.bs.find('h1')

		# clear version tags
		for t in tag.find_all('span'):
			t.decompose()

		split = tag.text.split(' / ')

		for idx, part in enumerate(split):
			split[idx] = part.strip()

		split = self.transform_names(split)

		return split

	def get_syntax(self):
		syntax = self.bs.find('pre', class_='Syntax')

		if syntax is None:
			return None

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


class MiscHandler(BaseHandler):
	async def parse(self):
		await self.handler([self.get_name()], self.file, self.get_desc())

	def get_name(self):
		return self.bs.find('h1').text


class ObjectHandler(MiscHandler):
	pass


class CommandListHandler(BaseHandler):
	async def parse(self):
		for tag in self.bs.find_all('h3', id=True):
			for span in tag.find_all('span'):
				span.decompose()

			name = tag.text.strip()
			desc = tag.next_element.next_element.next_element
			syntax = self.bs.find('span', class_='func', string=name)

			if syntax is not None:
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
					names.append(', '.join(text.strip() for text in td.text.split('\n')))
				elif idx == 1:
					desc = self.pretty_desc(td)
				else:
					break

			# if the id has some other searchable data that
			# isn't just the var name without the A_ we add it
			if tag['id'] != names[0][2:]:
				names.append(tag['id'])

			await self.handler(names, f"{self.file}#{tag['id']}", desc)
