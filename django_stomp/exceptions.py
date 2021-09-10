class CorrelationIdNotProvidedException(Exception):
    pass


class DjangoStompImproperlyConfigured(Exception):
    pass


class DjangoStompIncorrectUse(Exception):
    """
    Raised when Django stomp has been invoked in a wrong manner such as
    less arguments than it needs, etc.
    """

    pass
