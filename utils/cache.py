from functools import wraps

def cache():
	cache = dict()

	def clear():
		cache.clear()

	def clear_by_arg(index, value):
		to_remove = []
		for key, (args, kwargs, return_value) in cache.items():
			if args[index] == value:
				to_remove.append(key)
		for key in to_remove:
			del cache[key]

	def clear_by_kwarg(key, value):
		to_remove = []
		for hash, (args, kwargs, return_value) in cache.items():
			if kwargs[key] == value:
				to_remove.append(hash)
		for hash in to_remove:
			del cache[hash]

	def wrapper(func):
		@wraps(func)
		async def wrapped(*args, **kwargs):
			key = list(args)
			for item in kwargs.items():
				key.append(item)
			key = hash(tuple(key))

			if key in cache:
				print('found in cache.')
				return cache[key][2]

			# not found, run it to get value

			value = await func(*args, **kwargs)
			cache[key] = (args, kwargs, value)
			return value

		wrapped.clear = clear
		wrapped.clear_by_arg = clear_by_arg
		wrapped.clear_by_kwarg = clear_by_kwarg

		return wrapped
	return wrapper
