FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

COPY rssrob/ rssrob/
COPY web/ web/
COPY config.example.yaml ./

RUN groupadd -g 1000 rssrob \
    && useradd -r -u 1000 -g rssrob -s /sbin/nologin rssrob \
    && mkdir -p configs var/feeds \
    && chown -R rssrob:rssrob /app

COPY docker-entrypoint.sh ./

USER rssrob

EXPOSE 8080 5000

ENTRYPOINT ["./docker-entrypoint.sh"]
