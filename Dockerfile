FROM python:3.10-bullseye

ENV LANG C.UTF-8

WORKDIR /usr/src/Aliyun-oss-sync

RUN apt-get update -y
RUN apt-get install -y screen tmux
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

RUN /usr/local/bin/python -m pip install --no-cache-dir --upgrade pip

COPY . .

RUN pip install --no-cache-dir -r requirements.txt