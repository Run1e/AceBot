from sanic import Request, Sanic
from sanic.response import HTTPResponse, json

app = Sanic('PyTorch API')


@app.post('/game')
async def game(request: Request):
	q = request.form.get('q', None)

	if q is None:
		return HTTPResponse(status=400)

	return json(dict(x='a'))


app.run('localhost', 80)
