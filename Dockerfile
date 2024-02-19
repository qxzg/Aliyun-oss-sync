FROM python:3.12-bookworm

ENV LANG C.UTF-8

WORKDIR /app

COPY . .

RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list \
    && echo "#deb-src https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "#deb-src https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "#deb-src https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "#deb-src https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && mkdir ~/.pip/ \
    && echo "[global]" > ~/.pip/pip.conf \
    && echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> ~/.pip/pip.conf \
    && echo "[install]" >> ~/.pip/pip.conf \
    && echo "trusted-host=mirrors.aliyun.com" >> ~/.pip/pip.conf


RUN apt-get update -y \
    && apt-get install -y --no-install-recommends tmux vim \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    &&pip install --no-cache-dir -r requirements.txt


CMD ["/bin/bash", "-c", "while true;do sleep 9999999;done"]
