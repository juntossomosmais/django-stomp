"""
Collection of exceptions that can be raised by django-stomp.
"""


class CorrelationIdNotProvidedException(Exception):
    """
    Raised when correlation-id has not been found and django-stomp is configured to raise in this scenario.
    """


class DjangoStompImproperlyConfigured(Exception):
    """
    Raised when django-stomp has been improperly configured with some settings or when a config was not found.
    """


class DjangoStompIncorrectUse(Exception):
    """
    Raised when Django stomp has been invoked in a wrong manner such as less arguments than it needs, etc.
    """
