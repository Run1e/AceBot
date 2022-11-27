FROM python:3.7

COPY requirements.txt /
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py .
COPY model.py .
COPY text_processor.py .
COPY torch_config.py .
COPY model.pth .
COPY embeddings embeddings

CMD ["python3", "-u", "api.py"]
