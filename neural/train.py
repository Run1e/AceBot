import glob
import os
import pickle

import torch
from dataset import Sequencer, TextDataset
from text_processor import TextProcessor
from torch import nn
from torch.utils.data import DataLoader
from torch_config import CORPUS_DIR, EMBEDDINGS_DIR
from torchtext.data.utils import get_tokenizer
from tqdm import tqdm

from model import TextCNN

DATA_SPLIT = 0.75
SEQUENCE_LEN = 380


def main():
    device = torch.device("cuda")

    embedding_vectors = torch.load(f"{EMBEDDINGS_DIR}/vectors.pkl")

    text_processor = TextProcessor(
        wti=pickle.load(open(f"{EMBEDDINGS_DIR}/wti.pkl", "rb")),
        tokenizer=get_tokenizer("basic_english"),
        standardize=True,
        min_len=3,
    )

    dataset = TextDataset(CORPUS_DIR, text_processor)

    # split into training and test set
    # TODO: fix this splitting sometimes failing when corpus size changes
    train_set, test_set = torch.utils.data.random_split(
        dataset,
        [int(len(dataset) * DATA_SPLIT), int(len(dataset) * (1.0 - DATA_SPLIT))],
    )

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
        weights=weights, num_samples=len(train_set), replacement=True
    )

    train_loader = DataLoader(
        dataset=train_set,
        batch_size=32,
        collate_fn=Sequencer(SEQUENCE_LEN),
        sampler=sampler,
    )

    test_loader = DataLoader(dataset=test_set, batch_size=32, collate_fn=Sequencer(SEQUENCE_LEN))

    # number of filters in each convolutional filter
    N_FILTERS = 64

    # sizes and number of convolutional layers
    FILTER_SIZES = [2, 3]

    # dropout for between conv and dense layers
    DROPOUT = 0.5

    model = TextCNN(
        embeddings=embedding_vectors,
        n_filters=N_FILTERS,
        filter_sizes=FILTER_SIZES,
        dropout=DROPOUT,
    ).to(device)

    print(model)
    print(
        "Trainable params:",
        sum(p.numel() for p in model.parameters() if p.requires_grad),
    )

    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    EPOCHS = 12

    best_acc = 0.0

    # training loop
    for epoch in range(EPOCHS):
        print("Epoch", epoch + 1)

        for i, data in tqdm(enumerate(train_loader), total=len(train_loader)):
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
                for file in glob.glob("models/model_*.pth"):
                    os.remove(file)
                torch.save(model.state_dict(), f"models/state_{epoch}.pth")

            print()
            print("Correct:", f"{correct}/{correct + wrong}", "Accuracy:", acc)
            print("[[TN, FP], [FN, TP]]")
            print(m)
            print()

    # put into evaluation mode
    model.eval()

    text_processor.do_standardize = True

    with torch.no_grad():
        while True:
            text = input("Prompt: ")
            x = text_processor.process(text)
            x = torch.tensor(x).unsqueeze(dim=0)
            print(model(x.to(device)).squeeze())


if __name__ == "__main__":
    if not os.path.isdir("models"):
        os.mkdir("models")
    main()
