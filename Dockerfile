FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

COPY rssrob/ rssrob/
COPY web/ web/
COPY config.example.yaml ./

EXPOSE 5000

ENTRYPOINT ["python", "-m", "rssrob"]
