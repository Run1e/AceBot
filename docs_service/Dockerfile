FROM python:3.11.2

RUN mkdir app
WORKDIR /app

COPY parser_instances .
COPY aggregator.py .
COPY api.py .
COPY parsers.py .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "-u", "api.py"]