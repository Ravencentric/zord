"""Read environment variables in task files."""

import os
from typing import overload


@overload
def get(name: str, /, *, default: str) -> str: ...


@overload
def get(name: str, /, *, default: None = None) -> str | None: ...


def get(name: str, /, *, default: str | None = None) -> str | None:
    """Read a value unchanged, using the default only when it is missing."""
    return os.environ.get(name, default)


def has(name: str, /) -> bool:
    """Check whether a variable exists, including when its value is empty."""
    return name in os.environ


def flag(name: str, /, *, default: bool = False) -> bool:
    """Read a boolean flag, raising ValueError for an invalid value."""
    value = os.environ.get(name)
    if value is None:
        return default

    match value.strip().lower():
        case "1" | "true" | "yes" | "on":
            return True
        case "0" | "false" | "no" | "off":
            return False
        case _:
            raise ValueError(f"environment variable {name!r} must be a boolean")
