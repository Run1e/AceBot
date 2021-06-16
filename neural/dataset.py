import os

import torch
from torch.utils.data import Dataset


def pad(tokens, seq_len):
	# pad([3, 6, 4], 5) -> [3, 6, 4, 0, 0]
	out = torch.zeros(seq_len, dtype=torch.int64)
	out[:len(tokens)] = tokens
	return out


class TextDataset(Dataset):
	def __init__(self, folder, processor):
		self.texts = list()
		self.labels = list()
		self.tokenized = dict()

		self.processor = processor

		# load corpus into .texts and .labels
		for dir, subdir, files in os.walk(folder):
			dir = dir.replace(r'\\', '/')

			for file in files:
				with open(f'{dir}/{file}', 'r', encoding='utf-8') as f:
					text = f.read()

				if not len(text):
					continue

				self.texts.append(text)

				label = int(dir[-1])
				self.labels.append(label)

	def get_tokens(self, item):
		tokens = self.tokenized.get(item, None)

		if tokens is None:
			tokens = self.processor.process(self.texts[item])
			self.tokenized[item] = tokens

		return tokens

	def __len__(self):
		return len(self.texts)

	def __getitem__(self, item):
		# get a data point from the loader

		# get the tokens for this item
		tokens = self.get_tokens(item)

		# get the label for this item
		label = self.labels[item]

		# return tokens and the labels as a FloatTensor
		return tokens, torch.tensor(label, dtype=torch.float32)


class Sequencer:
	def __init__(self, sequence_len):
		self.sequence_len = sequence_len

	def __call__(self, batch):
		# sort the batch from longest to shortest sentences
		# not necessarily necessary for convnet but is for LSTM layer with padding and packing
		batch = sorted(batch, key=lambda x: x[0].size(), reverse=True)

		# strip tokens
		tokens = [token_list for token_list, _ in batch]
		# and pad and stack into a LongTensor
		tokens = torch.stack([pad(token_list, self.sequence_len) for token_list in tokens])

		# strip labels
		labels = torch.tensor([label for _, label in batch], dtype=torch.float32)

		return tokens, labels
