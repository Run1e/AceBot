import json
from fuzzywuzzy import fuzz, process

with open('data/Docs.json', 'r', encoding='utf-8-sig') as f:
	docs = json.loads(f.read())


def docs_search(search_terms):
	queries = search_terms.splitlines()

	# Finds a documentation page with fuzzy search
	def find_page(query):
		matches = process.extract(
			query,
			docs.keys(),
			scorer=fuzz.partial_ratio,
			limit=99999
		)

		for match, score in matches:
			if query.upper() == ''.join(filter(str.isupper, match)) or match.lower().startswith(query.lower()):
				return match

		return matches[0][0]

	results = {}

	for query in queries:
		page = find_page(query)
		obj = docs.get(page, None)
		if obj is not None:
			results[page] = obj

	return results
