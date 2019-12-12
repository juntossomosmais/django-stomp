# Django Stomp

[![Build Status](https://dev.azure.com/juntos-somos-mais-loyalty/python/_apis/build/status/django-stomp?branchName=master)](https://dev.azure.com/juntos-somos-mais-loyalty/python/_build/latest?definitionId=23&branchName=master)
[![Maintainability](https://api.codeclimate.com/v1/badges/381136911e038d1a6887/maintainability)](https://codeclimate.com/github/juntossomosmais/django-stomp/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/381136911e038d1a6887/test_coverage)](https://codeclimate.com/github/juntossomosmais/django-stomp/test_coverage)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

A simple implementation of STOMP with Django.

In theory it can work with any broker which supports STOMP with none or minor adjustments.

## Installation

`pip install django_stomp`

Add `django_stomp` in your `INSTALLED_APPS` and so be it.

## Configuration process

Not yet fully available, but feel free to see our tests to get insights.

### Consumer

First you must create a function which receives an parameter of type `django_stomp.services.consumer.Payload`. Let's suppose the module `app.sample` with the following content:

```python
import logging

from django_stomp.services.consumer import Payload

logger = logging.getLogger(__name__)


def my_honest_logic(payload: Payload) -> None:
    logger.info("Yeah, I received a payload from django-stomp!")

    my_payload = payload.body
    my_header = payload.headers

    if my_payload.get("my-dict-key"):
        payload.ack()
    else:
        logger.info("To DLQ!")
        payload.nack()
```

Now you must provide broker connection details filling out the following parameters at least:

- STOMP_SERVER_HOST
- STOMP_SERVER_PORT
- STOMP_USE_SSL

And just create the job issuing the following command:

```bash
python manage.py pubsub "/queue/your-stuff" app.sample.my_honest_logic
```

That's it ✌️

## Tests

In order to execute tests for ActiveMQ, execute the following:

    docker-compose up -d broker-activemq
    
Or for RabbitMQ:

    docker-compose up -d broker-rabbitmq
    
Then at last:

    pipenv run tox
