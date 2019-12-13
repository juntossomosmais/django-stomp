import functools
import time
from typing import Dict


def slow_down(_func=None, *args, **kwargs):
    """Sleep given amount of seconds before calling the function"""

    before = kwargs.get("before", 0.5)
    after = kwargs.get("after", 0.5)

    def decorator_slow_down(func):
        @functools.wraps(func)
        def wrapper_slow_down(*args, **kwargs):
            time.sleep(before)
            value = func(*args, **kwargs)
            time.sleep(after)
            return value

        return wrapper_slow_down

    if _func is None:
        return decorator_slow_down
    else:
        return decorator_slow_down(_func)


def eval_str_as_boolean(value: str):
    return str(value).lower() in ("true", "1", "t", "y")


def return_none_if_provided_value_is_falsy_or_strange(value):
    if value is not None and (value == "" or value == b"" or value in (".", "none")):
        return None
    return value


def clean_dict_with_falsy_or_strange_values(value: Dict) -> Dict:
    return {k: v for k, v in value.items() if return_none_if_provided_value_is_falsy_or_strange(v)}


def eval_as_int_otherwise_none(value):
    return int(value) if value else None


def only_destination_name(destination: str) -> str:
    position = destination.rfind("/")
    if position > 0:
        return destination[position + 1 :]
    return destination


def create_dlq_destination_from_another_destination(destination: str) -> str:
    return f"DLQ.{only_destination_name(destination)}"
