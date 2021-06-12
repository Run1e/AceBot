import pickle

import torch

from torch_config import GLOVE_DIR

idx = 0
word2idx = {}
glove_size = 1193517
vectors = torch.empty((glove_size, 100), dtype=torch.float32)

with open(f'{GLOVE_DIR}/glove.twitter.27B.100d.txt', 'rb') as f:
	for l in f:
		line = l.decode().split()
		if len(line) != 101:
			continue
		word = line[0]
		word2idx[word] = idx
		c = line[1:]
		vector = torch.tensor([float(x) for x in c], dtype=torch.float32)
		vectors[idx] = vector
		idx += 1

pickle.dump(word2idx, open(f'{GLOVE_DIR}/word2idx.pkl', 'wb'))
torch.save(vectors, f'{GLOVE_DIR}/vectors.pkl')
