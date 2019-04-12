import re

class BaseHandler:
	def __init__(self, bs, path, handler):
		self.file = path
		self.handler = handler
		self.bs = bs

	def get_desc(self):
		p = self.bs.find('p')

		if p is None:
			return None

		return p.text

	def pretty_syntax(self, syntax):
		span_list = syntax.find_all('span', class_='optional')

		for span in span_list:
			span.replace_with(f'[{span.text}]')

		return syntax.text.strip().split('\n')

class CommandsHandler(BaseHandler):
	async def parse(self):
		await self.handler(
			self.get_names(),
			self.file,
			self.get_desc(),
			self.get_syntaxes(),
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

	def get_syntaxes(self):
		syntax = self.bs.find('pre', class_='Syntax')

		if syntax is None:
			return None

		return self.pretty_syntax(syntax)

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
			desc = tag.next_element.next_element.next_element.text

			syntax = self.bs.find('span', class_='func', string=name)
			syntax = None if syntax is None else [syntax.parent.text]

			await self.handler([name], f'{self.file}#{name}', desc, syntax)