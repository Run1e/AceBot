import os
import pickle
from collections import Counter

import torch
from torchtext.data.utils import get_tokenizer
from tqdm import tqdm

from torch_config import CORPUS_DIR, EMBEDDINGS_DIR, GLOVE_DIR

tokenizer = get_tokenizer("basic_english")
counter = Counter()

for dir, subdir, files in os.walk(CORPUS_DIR):
    dir = dir.replace(r"\\", "/")

    print("\nReading:", dir)
    for file in tqdm(files):
        with open(f"{dir}/{file}", "r", encoding="utf-8") as f:
            text = f.read()

        if not len(text):
            continue

        counter.update(tokenizer(text))

glove_wti: dict = pickle.load(open(f"{GLOVE_DIR}/word2idx.pkl", "rb"))
glove_vectors: torch.Tensor = torch.load(f"{GLOVE_DIR}/vectors.pkl")

embed_idx = 0
embed_wti = dict()
embed_vectors = []

print("Copying relevant embeddings...")
for word in counter.keys():
    glove_idx = glove_wti.get(word, None)

    if glove_idx is None:
        continue

    embed_wti[word] = embed_idx
    embed_vectors.append(glove_vectors[glove_idx])
    embed_idx += 1

if not os.path.exists(EMBEDDINGS_DIR):
    os.mkdir(EMBEDDINGS_DIR)

pickle.dump(embed_wti, open(f"{EMBEDDINGS_DIR}/wti.pkl", "wb"))
torch.save(torch.stack(embed_vectors), f"{EMBEDDINGS_DIR}/vectors.pkl")
