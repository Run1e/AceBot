import torch
import torch.nn as nn
import torch.nn.functional as F


class TextCNN(nn.Module):
    def __init__(self, embeddings, n_filters, filter_sizes, dropout):
        super().__init__()

        num_embeddings = embeddings.size(0)
        embedding_dim = embeddings.size(1)

        self.embedding = nn.Embedding(num_embeddings, embedding_dim, padding_idx=0, sparse=False)
        self.embedding.load_state_dict(dict(weight=embeddings))
        # self.embedding.weight.requires_grad = False

        self.convs = nn.ModuleList(
            [
                nn.Conv2d(
                    in_channels=1,
                    out_channels=n_filters,
                    kernel_size=(fs, embedding_dim),
                )
                for fs in filter_sizes
            ]
        )

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
