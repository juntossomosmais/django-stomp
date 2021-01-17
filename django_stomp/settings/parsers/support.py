"""
Parser supporting functions.
"""
from distutils.util import strtobool
from typing import Any

from django_stomp.exceptions import DjangoStompImproperlyConfigured


def get_config_or_default(django_config, env_name, default_value) -> Any:
    """
    Gets an env variable or returns a default value.
    """
    env_value = getattr(django_config, env_name, None)

    if env_value is None:
        return default_value

    return env_value


def get_config_or_exception(django_config, env_name) -> Any:
    """
    Gets an env variable or raises an exception.
    """
    env_value = getattr(django_config, env_name, None)

    if env_value is None:
        raise DjangoStompImproperlyConfigured("Missing required env var is missing: %s", env_name)

    return env_value


def get_config_as_bool_or_default(django_config, env_name, default_value) -> bool:
    """
    Evals env var strings as booleans.
    """
    env_var = get_config_or_default(django_config, env_name, default_value)

    return bool(strtobool(env_var))
