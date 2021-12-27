FROM python:3.9.9

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ADD . .

CMD ["python3", "-u", "main.py"]