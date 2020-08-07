FROM python:3.7-slim-stretch

WORKDIR /django-stomp-lib

COPY . /django-stomp-lib

RUN pip install pipenv && \
    pipenv install --system --ignore-pipfile --dev