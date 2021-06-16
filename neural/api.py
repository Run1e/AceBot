import pickle

import torch
from sanic import Request, Sanic
from sanic.response import HTTPResponse, json
from torchtext.data.utils import get_tokenizer

from model import TextCNN
from text_processor import TextProcessor
from torch_config import EMBEDDINGS_DIR

app = Sanic('PyTorch API')

embeddings = torch.load(f'{EMBEDDINGS_DIR}/vectors.pkl')

model = TextCNN(
	embeddings=embeddings,
	n_filters=64,
	filter_sizes=[2, 3],
	dropout=0.0,
)

device = torch.device('cpu')
model.load_state_dict(torch.load('model_state.pth', map_location=device))
model.eval()

text_processing = TextProcessor(
	wti=pickle.load(open(f'{EMBEDDINGS_DIR}/wti.pkl', 'rb')),
	tokenizer=get_tokenizer('basic_english'),
	standardize=True,
)


@app.post('/game')
async def game(request: Request):
	q = request.form.get('q', None)

	if q is None:
		return HTTPResponse(status=400)

	tokens = text_processing.process(q)
	x = torch.unsqueeze(tokens, dim=0)

	pred = model(x)
	pred = torch.squeeze(pred).item()

	return json(dict(p=pred))


app.run('localhost', 80)
