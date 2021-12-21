import disnake
import ast

from datetime import datetime, timedelta


class DiscordLookup:
	def __init__(self, ctx, query):
		self.ctx = ctx
		self.query = query

		all_roles = list(reversed(ctx.guild.roles[1:]))

		self.namespace = dict(
			bot=ctx.bot,
			guilds=ctx.bot.guilds,
			channel=ctx.channel,
			guild=ctx.guild,
			author=ctx.author,
			message=ctx.message,
			members=ctx.guild.members,
			emojis=ctx.guild.emojis,
			channels=ctx.guild.channels,
			roles=all_roles,
		)

		self.funcs = dict(
			st=disnake.utils.snowflake_time,
			now=datetime.utcnow,
			dt=datetime,
			td=timedelta,
			str=str,
			list=list,
			int=int,
			repr=repr,
			len=len,
			sum=sum,
			sorted=sorted,
			excel_time=lambda dt: dt.strftime('%d.%m.%y %H:%M'),
			past=lambda *args, **kwargs: datetime.utcnow() - timedelta(*args, **kwargs),
			guild=lambda ident: self.get_object(ctx.bot.guilds, ident),
			role=lambda ident: self.get_object(all_roles, ident),
			member=lambda ident: self.get_object(ctx.guild.members, ident),
			user=lambda ident: self.get_object(ctx.bot.users, ident),
			channel=lambda ident: self.get_object(list(ctx.bot.get_all_channels()), ident),
			emoji=lambda ident: self.get_object(ctx.guild.emojis, ident),
		)

	def get_object(self, items, ident):
		if isinstance(ident, int):
			res = disnake.utils.get(items, id=ident)
		elif isinstance(ident, str):
			res = disnake.utils.get(items, name=ident) or disnake.utils.get(items, display_name=ident)
		else:
			raise TypeError('Can\'t find items with ident of type \'{}\''.format(type(ident)).__name__)

		if res is None:
			raise ValueError('No item with ident equal to \'{}\''.format(ident))

		return res

	def run(self):
		self.ast = ast.parse(self.query)
		#print(ast.dump(self.ast))
		return self.traverse(self.ast.body[0].value)

	def traverse(self, node):
		if isinstance(node, ast.Str):
			return node.s

		elif isinstance(node, ast.Num):
			return node.n

		elif isinstance(node, ast.NameConstant):
			return node.value

		elif isinstance(node, ast.Name):
			return self.get_namespace(node.id)

		elif isinstance(node, ast.Call):
			func = self.get_func(node.func.id)
			args = [self.traverse(arg_val) for arg_val in node.args]
			kwargs = {kw.arg: self.traverse(kw.value) for kw in node.keywords}
			return func(*args, **kwargs)

		elif isinstance(node, ast.Subscript):
			if hasattr(node, 'value'):
				items = self.traverse(node.value)
			else:
				raise NotImplementedError('Those slices not implemented.')

			if not isinstance(items, list):
				raise ValueError('Can only perform queries on lists.')

			if not items:
				return items

			if hasattr(node.slice, 'value'):
				items = self.filter_items(items, node.slice.value)
			else:

				if node.slice.lower is not None:
					items = self.filter_items(items, node.slice.lower)

				if node.slice.upper is not None:
					if not isinstance(node.slice.upper, ast.Name):
						raise TypeError('Slice attribute token has to be an attribute lookup.')

					items = sorted(items, key=lambda item: getattr(item, node.slice.upper.id))

				if node.slice.step is not None:
					if not isinstance(node.slice.step, ast.Name):
						raise TypeError('Slice order token has to be an attribute lookup.')

					items = list(getattr(item, node.slice.step.id) for item in items)

			return items

		elif isinstance(node, ast.Attribute):
			val = self.traverse(node.value)
			return getattr(val, node.attr)

		elif isinstance(node, ast.BinOp):
			left = self.traverse(node.left)
			right = self.traverse(node.right)

			if isinstance(node.op, ast.Add):
				return left + right
			elif isinstance(node.op, ast.Sub):
				return left - right
			elif isinstance(node.op, ast.Mult):
				return left * right
			elif isinstance(node.op, ast.Div):
				return left / right
			elif isinstance(node.op, ast.FloorDiv):
				return left // right
			else:
				raise NotImplementedError('Operator: {}'.format(node.op))

		else:
			raise NotImplementedError('Unsupported AST type: \'{}\''.format(node))

	def get_func(self, name):
		try:
			return self.funcs[name]
		except KeyError:
			raise ValueError('Namespace resolve failure: \'{}\''.format(name))

	def get_namespace(self, name):
		try:
			return self.namespace[name]
		except KeyError:
			raise ValueError('Namespace resolve failure: \'{}\''.format(name))

	def filter_items(self, items, node):
		if isinstance(node, ast.Compare):
			return self.filter_compare(items, node.ops, node.left, node.comparators)

		elif isinstance(node, ast.BoolOp):
			return self.filter_boolop(items, node.op, node.values)

		elif isinstance(node, ast.UnaryOp):
			return self.filter_unaryop(items, node.op, node.operand)

		elif isinstance(node, ast.Name):
			return list(filter(lambda item: getattr(item, node.id), items))

		else:
			return items

	def filter_unaryop(self, items, op, operand):
		if not isinstance(operand, ast.Name):
			raise NotImplementedError('Only attrs allowed with unary not')

		op_res = operand.id
		new_list = list()

		for item in items:
			res = getattr(item, op_res)

			if isinstance(op, ast.Not):
				if not res:
					new_list.append(item)
			else:
				raise NotImplementedError('Unary operator: {}'.format(op))

		return new_list

	def filter_boolop(self, items, op, values):
		method = 'intersection' if isinstance(op, ast.And) else 'union'

		fin = list()

		for idx, value in enumerate(values):
			new = self.filter_items(items, value)

			if idx == 0:
				fin = new
			else:
				fin = list(getattr(set(fin), method)(new))

		return fin

	def filter_compare(self, items, ops, left, comparators):
		return list(filter(lambda item: self.perform_compare(item, ops, left, comparators), items))

	def perform_compare(self, item, ops, left, comparators):
		left = self.get_compare_value(item, left)

		for op, comparator in zip(ops, comparators):
			right = self.get_compare_value(item, comparator)

			if isinstance(op, ast.Eq) and not left == right:
				return False
			elif isinstance(op, ast.NotEq) and not left != right:
				return False
			elif isinstance(op, ast.Gt) and not left > right:
				return False
			elif isinstance(op, ast.GtE) and not left >= right:
				return False
			elif isinstance(op, ast.Lt) and not left < right:
				return False
			elif isinstance(op, ast.LtE) and not left <= right:
				return False
			elif isinstance(op, ast.In) and not left in right:
				return False
			elif isinstance(op, ast.NotIn) and left in right:
				return False

			left = right

		return True

	def get_compare_value(self, item, node):
		if isinstance(node, ast.Name):
			if hasattr(item, node.id):
				return getattr(item, node.id)
			else:
				return self.get_namespace(node)
		else:
			return self.traverse(node)
