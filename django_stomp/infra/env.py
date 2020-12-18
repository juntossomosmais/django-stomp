"""
Environment variables reading functions.
"""
from distutils.util import strtobool
from typing import Any
from django.conf import settings


class DjangoStompMissingRequiredConfig(Exception):
    """
    Raised when a required django settings variable was not found.
    """


def get_config_or_default_any(env_name: str, default_value: Any) -> Any:
    """
    Gets an env variable or returns a default value.
    """
    env_value = getattr(settings, env_name, None)

    if env_value is None:
        return default_value

    return env_value


def get_config_or_default(env_name: str, default_value: str) -> str:
    """
    Gets an env variable or returns a default value.
    """
    env_value = getattr(settings, env_name, None)

    if env_value is None:
        return default_value

    return env_value


def get_config_or_exception(env_name: str) -> str:
    """
    Gets an env variable or raises an exception.
    """
    env_value = getattr(settings, env_name, None)

    if env_value is None:
        raise DjangoStompMissingRequiredConfig("Missing required env var is missing: %s", env_name)

    return env_value


def get_config_as_bool_or_default(env_name: str, default_value: str) -> bool:
    """
    Evals env var strings as booleans.
    """
    env_var = get_config_or_default(env_name, default_value)

    return strtobool(env_var)
