FROM python:3

COPY requirements.txt ./

RUN pip install -U git+https://github.com/Rapptz/discord.py@rewrite#egg=discord.py
RUN pip install --no-cache-dir -r requirements.txt

ADD . .

CMD [ "python3", "-u", "bot.py" ]