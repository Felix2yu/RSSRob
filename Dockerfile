FROM python:3.12-slim AS base

WORKDIR /app

ENV TZ=Asia/Shanghai
RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime

COPY requirements.txt ./
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

COPY rssrob/ rssrob/
COPY config.example.yaml ./

RUN groupadd -g 1000 rssrob \
    && useradd -r -u 1000 -g rssrob -d /app -s /sbin/nologin rssrob \
    && mkdir -p configs var/feeds \
    && chown -R rssrob:rssrob /app

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

USER rssrob

EXPOSE 5000

ENTRYPOINT ["/bin/sh", "./docker-entrypoint.sh"]
