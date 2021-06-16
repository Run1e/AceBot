import re
import string

import torch
from unidecode import unidecode


class TextProcessor:
	def __init__(self, wti, tokenizer, standardize=True):
		self.wti = wti
		self.tokenizer = tokenizer
		self.do_standardize = standardize

	def process(self, text):
		# converts a string to a list of word indices, using the tokenizer and "word to index" map
		text = self.standardize(text) if self.do_standardize else text
		return torch.LongTensor([self.wti.get(word, 1) for word in self.tokenizer(text)])

	@staticmethod
	def standardize(s: str):
		# make lowercase
		s = s.lower()

		# remove urls
		s = re.sub(r'^https?:\/\/.*[\r\n]*', '', s, flags=re.MULTILINE)

		# remove diacritics
		s = unidecode(s)

		# remove numbers
		s = re.sub(f'[{string.digits}\.,]', ' ', s)

		# remove punctuation
		s = re.sub(f'[{re.escape(string.punctuation)}]', '', s)

		# condense whitespaces
		s = re.sub(r'\s+', ' ', s)

		return s.lower().strip()
