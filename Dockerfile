FROM python:3.10-bullseye

ENV LANG C.UTF-8

WORKDIR /usr/src/Aliyun-oss-sync

COPY . .

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends python-dev screen vim ssh iputils-ping net-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && cd && mkdir .ssh && chmod 700 .ssh/ && cd .ssh \
    && wget -O authorized_keys https://raw.githubusercontent.com/qxzg/shell/master/other/authorized_keys \
    && chmod 600 authorized_keys \
    && cd /etc/ssh \
    && sed -i -e "s/#PubkeyAuthentication yes/PubkeyAuthentication yes/g" sshd_config \
    && sed -i -e "s/PasswordAuthentication yes/PasswordAuthentication no/g" sshd_config \
    && sed -i -e "s/#Port/Port/g" /etc/ssh/sshd_config \
    && sed -i -e "s/Port 22/Port 8848/g" /etc/ssh/sshd_config \
    && echo "Protocol 2" >> sshd_config \
    && cp /usr/src/Aliyun-oss-sync/units/init_docker.sh /root/init_docker.sh

EXPOSE 8848

RUN /usr/local/bin/python -m pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pyinstaller

CMD ["/bin/bash", "/root/init_docker.sh"]