# Django Stomp

[![Build Status](https://dev.azure.com/juntos-somos-mais-loyalty/python/_apis/build/status/django-stomp?branchName=master)](https://dev.azure.com/juntos-somos-mais-loyalty/python/_build/latest?definitionId=23&branchName=master)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

A simple implementation of STOMP with Django.

## Installation

`pip install django_stomp`

Add `django_stomp` in your `INSTALLED_APPS` and so be it.

## Configuration process

Not yet available, but feel free to see our tests to get insights.


## Tests

In order to execute tests, first do the following:

    docker-compose up -d
    
Then:

    pipenv run tox
