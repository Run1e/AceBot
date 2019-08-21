import discord
import ast

from datetime import datetime, timedelta


class DiscordLookup:
	def __init__(self, ctx, query):
		self.ctx = ctx
		self.query = query

		all_roles = list(reversed(ctx.guild.roles[1:]))

		self.standard_namespace = dict(
			str=str,
			int=int,
			repr=repr,
			r=lambda ident: self.get_object(all_roles, ident),
			m=lambda ident: self.get_object(ctx.guild.members, ident),
			c=lambda ident: self.get_object(ctx.guild.channels, ident),
			e=lambda ident: self.get_object(ctx.guild.emojis, ident),
			bot=ctx.bot,
			channel=ctx.channel,
			guild=ctx.guild,
			author=ctx.author,
			message=ctx.message,
			st=discord.utils.snowflake_time,
			dt=datetime.utcnow,
			td=timedelta,
		)

		self.special_namespace = dict(
			rs=lambda: all_roles,
			ms=lambda: ctx.guild.members,
			cs=lambda: ctx.guild.channels,
			es=lambda: ctx.guild.emojis
		)

	def get_object(self, items, ident):
		ident_type = 'id' if isinstance(ident, int) else 'name'
		res = discord.utils.get(items, **{ident_type: ident})
		if res is None:
			raise ValueError('No item with {} equal to \'{}\''.format(ident_type, ident))
		return res

	def run(self):
		self.ast = ast.parse(self.query)
		#print(ast.dump(self.ast))
		return self.traverse(self.ast.body[0].value)

	def traverse(self, node):
		if isinstance(node, ast.Call):
			func = self.traverse(node.func)

			if not callable(func):
				raise SyntaxError('Not callable: \'{}\''.format(str(func)))

			if func in self.standard_namespace.values():
				args = [self.traverse(arg_val) for arg_val in node.args]
				kwargs = {kw.arg: self.traverse(kw.value) for kw in node.keywords}

				res = func(*args, **kwargs)

				if func not in self.special_namespace.values():
					return res

			elif func in self.special_namespace.values():
				items = func()

				if not node.args:
					return items

				return self.filter_items(items, node.args[0])

		elif isinstance(node, ast.Attribute):
			val = self.traverse(node.value)
			if isinstance(val, list):
				return list(getattr(item, node.attr) for item in val)
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

		elif isinstance(node, ast.Str):
			return node.s
		elif isinstance(node, ast.Num):
			return node.n
		elif isinstance(node, ast.Name):
			return self.get_namespace(node.id)
		elif isinstance(node, ast.NameConstant):
			return node.value
		else:
			raise NotImplementedError('Unsupported AST type: \'{}\''.format(node))

	def get_namespace(self, name):
		if name in self.standard_namespace:
			return self.standard_namespace[name]
		elif name in self.special_namespace:
			return self.special_namespace[name]
		raise ValueError('Namespace resolve failure: \'{}\''.format(name))

	def get_namespace_or_attr(self, item, node):
		try:
			return self.traverse(node)
		except ValueError:
			return getattr(item, node.id)

	def filter_items(self, items, node):
		if isinstance(node, ast.Compare):
			return self.filter_compare(items, node.ops, node.left, node.comparators)
		elif isinstance(node, ast.BoolOp):
			return self.filter_boolop(items, node.op, node.values)
		elif isinstance(node, ast.UnaryOp):
			return self.filter_unaryop(items, node.op, node.operand)
		elif isinstance(node, ast.Name):
			return list(filter(lambda item: getattr(item, node.id), items))

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
		left = self.get_namespace_or_attr(item, left)

		for op, comparator in zip(ops, comparators):
			right = self.get_namespace_or_attr(item, comparator)

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