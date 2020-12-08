FROM python:3.7

COPY requirements.txt ./
COPY tensorflow-2.3.1-cp37-cp37m-linux_x86_64.whl ./
RUN pip install tensorflow-2.3.1-cp37-cp37m-linux_x86_64.whl
RUN pip install --no-cache-dir -r requirements.txt

ADD . .

CMD ["python3", "-u", "ace.py"]