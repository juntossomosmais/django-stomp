FROM python:3.10-alpine

ENV PYTHONUNBUFFERED=1

RUN  apk -U upgrade && \
    apk add --no-cache git

WORKDIR /app
COPY . .

RUN pip install --upgrade pip && \
    pip install poetry && \
    poetry export -f requirements.txt -o requirements.txt --with dev && \
    pip uninstall --yes poetry && \
    pip install --no-cache-dir --upgrade --upgrade-strategy=eager -r requirements.txt

ENV PIPENV_IGNORE_VIRTUALENVS=1
# keep the container running
CMD ["tail", "-f", "/dev/null"]