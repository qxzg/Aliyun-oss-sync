FROM python:3.10-bullseye

ENV LANG C.UTF-8

WORKDIR /usr/src/Aliyun-oss-sync

RUN apt-get update -y&\
apt-get install -y screen tmux&\
apt-get clean&\
rm -rf /var/lib/apt/lists/*

COPY . .

RUN /usr/local/bin/python -m pip install --no-cache-dir --upgrade pip&\
pip install --no-cache-dir -r requirements.txt