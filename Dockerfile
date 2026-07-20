FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

COPY rssrob/ rssrob/
COPY web/ web/
COPY config.example.yaml ./

RUN useradd -r -s /sbin/nologin rssrob \
    && mkdir -p configs var/feeds \
    && chown -R rssrob:rssrob /app

USER rssrob

EXPOSE 8080

ENTRYPOINT ["python", "-m", "rssrob"]
