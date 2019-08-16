FROM python:3.7

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

ADD . .

CMD ["python3", "-u", "ace.py"]