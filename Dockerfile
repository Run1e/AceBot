FROM python:3.11.2

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY cogs cogs
COPY utils utils
COPY ace.py .
COPY main.py .

CMD ["python3", "-u", "main.py"]
