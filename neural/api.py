import pickle

import torch
from sanic import Request, Sanic
from sanic.response import HTTPResponse, json
from text_processor import TextProcessor
from torch_config import EMBEDDINGS_DIR
from torchtext.data.utils import get_tokenizer

from model import TextCNN

app = Sanic("torch_api")

embeddings = torch.load(f"{EMBEDDINGS_DIR}/vectors.pkl")

model = TextCNN(
    embeddings=embeddings,
    n_filters=64,
    filter_sizes=[2, 3],
    dropout=0.0,
)

device = torch.device("cpu")
model.load_state_dict(torch.load("model.pth", map_location=device))
model.eval()

text_processing = TextProcessor(
    wti=pickle.load(open(f"{EMBEDDINGS_DIR}/wti.pkl", "rb")),
    tokenizer=get_tokenizer("basic_english"),
    standardize=True,
    min_len=3,
)


@app.post("/game")
async def game(request: Request):
    q = request.form.get("q", None)

    if q is None:
        return HTTPResponse(status=400)

    tokens = text_processing.process(q)
    x = torch.unsqueeze(tokens, dim=0)

    pred = model(x)
    pred = torch.squeeze(pred).item()

    # TODO: add logging

    return json(dict(p=pred))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)
