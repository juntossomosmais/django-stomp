# Django Stomp

[![Build Status](https://dev.azure.com/juntos-somos-mais-loyalty/python/_apis/build/status/django-stomp?branchName=master)](https://dev.azure.com/juntos-somos-mais-loyalty/python/_build/latest?definitionId=23&branchName=master)
[![Maintainability](https://sonarcloud.io/api/project_badges/measure?project=juntossomosmais_django-stomp&metric=sqale_rating)](https://sonarcloud.io/dashboard?id=juntossomosmais_django-stomp)
[![Test Coverage](https://sonarcloud.io/api/project_badges/measure?project=juntossomosmais_django-stomp&metric=coverage)](https://sonarcloud.io/dashboard?id=juntossomosmais_django-stomp)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Downloads](https://pepy.tech/badge/django-stomp)](https://pepy.tech/project/django-stomp)
[![Downloads](https://pepy.tech/badge/django-stomp/month)](https://pepy.tech/project/django-stomp/month)
[![Downloads](https://pepy.tech/badge/django-stomp/week)](https://pepy.tech/project/django-stomp/week)
[![PyPI version](https://badge.fury.io/py/django-stomp.svg)](https://badge.fury.io/py/django-stomp)
[![GitHub](https://img.shields.io/github/license/mashape/apistatus.svg)](https://github.com/juntossomosmais/django-stomp/blob/master/LICENSE)

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

### Settings

Here is a list of parameters that you can set in your Django project settings:

***STOMP_SERVER_HOST***

  The hostname of the STOMP server.

***STOMP_SERVER_PORT***

  The STOMP server port used to allow STOMP connections.

***STOMP_SERVER_USER***

  The client username to connect to a STOMP server.

***STOMP_SERVER_PASSWORD***

  The client password to connect to a STOMP server.

***STOMP_USE_SSL***

  Set to ``True, true, 1, T, t, Y or y`` in order to all STOMP connections use a SSL/TLS tunnel.

***STOMP_SERVER_STANDBY_HOST***

  The hostname of the STOMP standby server.

***STOMP_SERVER_STANDBY_PORT***

  The STOMP standby server port used to allow STOMP connections.

***STOMP_SERVER_VHOST***

  The virtual host used in the STOMP server.

***STOMP_SUBSCRIPTION_ID***

  Used to identify the subscription in the connection between client and server. See the [STOMP protocol specification
](https://stomp.github.io/stomp-specification-1.1.html#SUBSCRIBE_id_Header) for more information.

***STOMP_OUTGOING_HEARTBEAT***

  A positive integer to indicates what is the period (in milliseconds) the client will send a frame to the server
that indicates its still alive. Set to ``0`` to means that it cannot send any heart-beat frame. See the [STOMP
protocol specification](https://stomp.github.io/stomp-specification-1.1.html#Heart-beating) for more information.
Defaults to 10000 ms.

***STOMP_INCOMING_HEARTBEAT***

  A positive integer to indicates what is the period (in milliseconds) the client will await for a server frame until
it assumes that the server is still alive. Set to ``0`` to means that it do not want to receive heart-beats. See
the [STOMP protocol specification](https://stomp.github.io/stomp-specification-1.1.html#Heart-beating) for more
information. Defaults to 10000 ms.

***STOMP_WAIT_TO_CONNECT***

  A positive integer to indicates how long it needs to await to try to reconnect if an `Exception` in the listener
logic is not properly handled.

***STOMP_DURABLE_TOPIC_SUBSCRIPTION***

  Set to ``True, true, 1, T, t, Y or y`` in order to all STOMP topic subscription be durable. See the [RabbitMQ](
https://www.rabbitmq.com/stomp.html#d.dts) take on it or the
[ActiveMQ](https://activemq.apache.org/how-do-durable-queues-and-topics-work) for more information.

***STOMP_LISTENER_CLIENT_ID***

  A string that represents the client id for a durable subscriber or the listener prefix client id in a non-durable
subscription in ActiveMQ.

***STOMP_CORRELATION_ID_REQUIRED***

  A flag that indicates if `correlation-id` header must be required or not. By default this flag is true (good practice
thinking in future troubleshooting).
Set to ``False, false, 0, F, f, N or n`` in order to allow consume messages without `correlation-id` header. If it's
false `django-stomp` generates a correlation-id header for the message automatically.

***STOMP_PROCESS_MSG_ON_BACKGROUND***

  A flag to indicate if it should process a received message on background, enabling the broker-consumer communication
to still take place.
  Set to ``True, true, 1, T, t, Y or y`` in order to have the message processing on background.

***STOMP_PROCESS_MSG_WORKERS***

  Optional parameter that controls how many workers the pool that manage the background processing should create. If
defined, this parameter **must** be an integer!

***STOMP_GRACEFUL_WAIT_SECONDS***

  Optional parameter that controls how many seconds django-stomp will wait for a message to be processed. Defaults to 30 seconds. If defined, this parameter **must** be an integer!

## Tests

In order to execute tests for ActiveMQ, execute the following:

    docker-compose up -d broker-activemq

Or for RabbitMQ:

    docker-compose up -d broker-rabbitmq

Then at last:

    pipenv run tox

## Database connection management (applies to version >= 5.0.0)

For every message that a `django-stomp` consumer receives, it opens a new DB connection if it needs to, keeping it open until it exceeds the maximum age defined by `CONN_MAX_AGE` or when the connection becomes unusable.

## Known limitations

- Currently, we assume that all dead lettered messages are sent to a queue with the same name as its original
destination but prefixed with `DLQ.`, i.e., if your queue is `/queue/some-queue`, the dead letter destination is
asssumed to be `/queue/DLQ.some-queue`.
- **Be cautious with the heartbeat functionality**! If your consumer is slow, it could prevent the client to receive
and process any `heart-beat` frame sent by the server, causing the client to terminate the connection due to a false
positive heartbeat timeout. You can workaround it with the `STOMP_PROCESS_MSG_ON_BACKGROUND` parameter that uses a
thread pool to process the message.
- For the RabbitMQ users: the **django-stomp consumer** always try to connect to a
[durable queue](https://www.rabbitmq.com/queues.html#durability), so if your queue is not durable, the RabbitMQ broker
will not allow the subscription.
- **For versions prior to 5.0.0**: Any database connection management in the consumer side is up to its callback. If you have any long-running consumer that relies on a DB connection, be sure that you manage it properly, otherwise if a connection becomes unusable, you'll have to restart the consumer entirely just to setup a new DB connection.
