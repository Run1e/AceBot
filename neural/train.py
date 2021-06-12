import os
import pickle

import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchtext.data.utils import get_tokenizer
from tqdm import tqdm

from data_standardizer import standardize
from torch_config import CORPUS_DIR, EMBEDDINGS_DIR

DATA_SPLIT = 0.75
SEQUENCE_LEN = 380


def pad(tokens, seq_len):
	# pad([3, 6, 4], 5) -> [3, 6, 4, 0, 0]
	out = torch.zeros(seq_len, dtype=torch.int64)
	out[:len(tokens)] = tokens
	return out


class TextDataset(Dataset):
	def __init__(self, folder):
		self.texts = list()
		self.labels = list()
		self.tokenized = dict()

		# text splitter
		self.tokenizer = get_tokenizer('basic_english')

		# word to index
		self.wti = pickle.load(open(f'{EMBEDDINGS_DIR}/wti.pkl', 'rb'))

		# word vectors
		self.vectors = torch.load(f'{EMBEDDINGS_DIR}/vectors.pkl')

		# load corpus into .texts and .labels
		for dir, subdir, files in os.walk(folder):
			dir = dir.replace(r'\\', '/')

			for file in files:
				with open(f'{dir}/{file}', 'r') as f:
					text = f.read()

				self.texts.append(text)

				label = int(dir[-1])
				self.labels.append(label)

	def text_to_tokens(self, text):
		# converts a string to a list of word indices, using the tokenizer and "word to index" map
		return torch.LongTensor([self.wti.get(word, 1) for word in self.tokenizer(text)])

	def get_tokens(self, item):
		tokens = self.tokenized.get(item, None)

		if tokens is None:
			tokens = self.text_to_tokens(self.texts[item])
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
	def __call__(self, batch):
		# sort the batch from longest to shortest sentences
		# not necessarily necessary for convnet but is for LSTM layer with padding and packing
		batch = sorted(batch, key=lambda x: x[0].size(), reverse=True)

		# strip tokens
		tokens = [token_list for token_list, _ in batch]
		# and pad and stack into a LongTensor
		tokens = torch.stack([pad(token_list, SEQUENCE_LEN) for token_list in tokens])

		# strip labels
		labels = torch.tensor([label for _, label in batch], dtype=torch.float32)

		return tokens, labels


class TextCNN(nn.Module):
	def __init__(self, embeddings, n_filters, filter_sizes, dropout):
		super().__init__()

		num_embeddings = embeddings.size(0)
		embedding_dim = embeddings.size(1)

		self.embedding = nn.Embedding(num_embeddings, embedding_dim, padding_idx=0, sparse=False)
		self.embedding.load_state_dict(dict(weight=embeddings))
		# self.embedding.weight.requires_grad = False

		self.convs = nn.ModuleList([
			nn.Conv2d(
				in_channels=1,
				out_channels=n_filters,
				kernel_size=(fs, embedding_dim))
			for fs in filter_sizes
		])

		self.dropout = nn.Dropout(dropout)
		self.fc = nn.Linear(len(filter_sizes) * n_filters, 1)
		self.sigmoid = nn.Sigmoid()

	def forward(self, x):
		# embedded = [batch_size, sequence_len, embedding_size] -> [32, 380, 100]
		embedded = self.embedding(x)
		embedded = embedded.unsqueeze(1)

		conved = [F.relu(conv(embedded)).squeeze(3) for conv in self.convs]
		pooled = [F.max_pool1d(conv, conv.shape[2]).squeeze(2) for conv in conved]

		x = self.dropout(torch.cat(pooled, dim=1))

		x = self.fc(x)
		return self.sigmoid(x)


def main():
	device = torch.device('cuda')

	dataset = TextDataset(f'{CORPUS_DIR}/proc')

	# split into training and test set
	# TODO: fix this splitting sometimes failing when corpus size changes
	train_set, test_set = torch.utils.data.random_split(dataset, [int(len(dataset) * DATA_SPLIT), int(len(dataset) * (1.0 - DATA_SPLIT))])

	# count number of samples in each class
	class_count = [0, 0]
	for data, label in dataset:
		class_count[int(label.item())] += 1

	# get relative weights for classes
	_sum = sum(class_count)
	class_count[0] /= _sum
	class_count[1] /= _sum

	# reverse the weights since we're getting the inverse for the sampler
	class_count = list(reversed(class_count))

	# set weight for every sample
	weights = [class_count[int(x[1].item())] for x in train_set]

	# weighted sampler
	sampler = torch.utils.data.WeightedRandomSampler(
		weights=weights,
		num_samples=len(train_set),
		replacement=True
	)

	train_loader = DataLoader(
		dataset=train_set,
		batch_size=32,
		collate_fn=Sequencer(),
		sampler=sampler
	)

	test_loader = DataLoader(
		dataset=test_set,
		batch_size=32,
		collate_fn=Sequencer()
	)

	# number of filters in each convolutional filter
	N_FILTERS = 64

	# sizes and number of convolutional layers
	FILTER_SIZES = [2, 3]

	# dropout for between conv and dense layers
	DROPOUT = 0.5

	model = TextCNN(
		embeddings=dataset.vectors,
		n_filters=N_FILTERS,
		filter_sizes=FILTER_SIZES,
		dropout=DROPOUT,
	).to(device)

	print(model)
	print('Trainable params:', sum(p.numel() for p in model.parameters() if p.requires_grad))

	criterion = nn.BCELoss()
	optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

	EPOCHS = 6

	best_acc = 0.0

	# training loop
	for epoch in range(EPOCHS):
		print('Epoch', epoch + 1)

		for i, data in tqdm(enumerate(train_loader)):
			# get word indices vector and corresponding labels
			x, labels = data

			# send to device
			x = x.to(device)
			labels = labels.to(device)

			# make predictions
			predictions = model(x).squeeze()

			# calculate loss
			loss = criterion(predictions, labels)

			# learning stuff...
			optimizer.zero_grad()
			loss.backward()
			optimizer.step()

		# evaluate
		with torch.no_grad():
			model.eval()

			correct = 0
			wrong = 0
			m = [[0, 0], [0, 0]]

			for data in test_loader:
				x, label = data
				x = x.to(device)

				predictions = model(x).squeeze()

				for truth, prediction in zip(label, predictions):
					y = int(truth.item())
					y_pred = 1 if prediction.item() > 0.5 else 0

					m[y][y_pred] += 1

					if y == y_pred:
						correct += 1
					else:
						wrong += 1

			model.train()

			acc = correct / (correct + wrong)
			if acc > best_acc:
				best_acc = acc
				torch.save(model.state_dict(), 'model_state.pth')

			print()
			print('Correct:', f'{correct}/{correct + wrong}', 'Accuracy:', acc)
			print('[[TN, FP], [FN, TP]]')
			print(m)
			print()

	# put into evaluation mode
	model.eval()

	with torch.no_grad():
		while True:
			text = input('Prompt: ')
			x = dataset.text_to_tokens(standardize(text))
			x = torch.tensor(x).unsqueeze(dim=0)
			print(model(x.to(device)).squeeze())


if __name__ == '__main__':
	main()
