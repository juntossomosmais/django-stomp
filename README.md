# Django Stomp

A simple implementation of Stomp with Django

## Install

`pip install django_stomp`

Add `django_stomp` in your `INSTALLED_APPS`

## Configure

```
STOMP_SERVER_HOST = os.getenv("STOMP_SERVER_HOST")
STOMP_SERVER_PORT = os.getenv("STOMP_SERVER_PORT")
```

Optionals

```
STOMP_SERVER_USER = os.getenv("STOMP_SERVER_USER")
STOMP_SERVER_PASSWORD = os.getenv("STOMP_SERVER_PASSWORD")
STOMP_USE_SSL = str(os.getenv("STOMP_USE_SSL", True)).lower() in ("true",)
LISTENER_CLIENT_ID = os.getenv("LISTENER_CLIENT_ID")
```