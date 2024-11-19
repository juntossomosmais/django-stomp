FROM python:3.9-slim-buster

ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y git

WORKDIR /app
COPY . .

RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry export -f requirements.txt -o requirements.txt --with dev && \
    pip uninstall --yes poetry && \
    pip install --no-cache-dir --upgrade --upgrade-strategy=eager -r requirements.txt
