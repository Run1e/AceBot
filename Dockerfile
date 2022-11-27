FROM python:3.9.9

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY cogs cogs
COPY utils utils
COPY ace.py .
COPY main.py .
COPY .git .git

CMD ["python3", "-u", "main.py"]
