from __future__ import annotations

import os
import shlex
import subprocess
import sys
from enum import IntEnum
from functools import cache
from typing import override


class Style(IntEnum):
    """
    Based on <https://en.wikipedia.org/wiki/ANSI_escape_code#Colors>
    """

    RESET = 0
    YELLOW = 33
    CYAN = 36
    RED = 31
    GREEN = 32
    MAGENTA = 35
    DIM = 90

    @property
    def marker(self) -> str:
        match self:
            case Style.RESET:
                return "[/]"
            case _:
                return f"[{self.name.lower()}]"

    def to_ansi(self) -> str:
        return f"\033[{self.value}m"

    @override
    def __str__(self) -> str:
        return self.to_ansi()


@cache
def can_colorize() -> bool:
    """Check env vars and for tty/dumb terminal"""

    if os.environ.get("ANSI_COLORS_DISABLED"):
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True

    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "fileno") or not hasattr(sys.stderr, "fileno"):
        return False

    try:
        return os.isatty(sys.stdout.fileno()) and os.isatty(sys.stderr.fileno())
    except OSError:
        return sys.stdout.isatty() and sys.stderr.isatty()


def render(s: str) -> str:
    color = can_colorize()

    for style in Style:
        if color:
            s = s.replace(style.marker, style.to_ansi())
        else:
            s = s.replace(style.marker, "")

    return s


def stdout(s: str, /) -> None:
    if s:
        s = render(s)
    print(s, file=sys.stdout, flush=True)


def stderr(s: str, /) -> None:
    if s:
        s = render(s)
    print(s, file=sys.stderr, flush=True)


def heading(name: str, /) -> None:
    stderr(f"[dim]──[/] [cyan]{name}[/]")


def command(program: str, /, *args: str, end: str = "\n") -> None:
    sys.stdout.flush()
    argv = []
    for arg in (program, *args):
        lines = arg.splitlines()
        first = lines[0] if lines else ""
        preview = []
        for char in first:
            if char.isprintable():
                preview.append(char)
            else:
                preview.append(repr(char)[1:-1])
        if first != arg:
            preview.append("...")
        argv.append("".join(preview))

    text = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
    prompt = render("[yellow]$[/]")
    print(f"\n{prompt} {text}", file=sys.stderr, end=end, flush=True)


def status(returncode: int, /) -> None:
    if returncode == 0:
        stderr("[green]✓[/] captured")
    else:
        stderr(f"[red]✗[/] exit {returncode}")


def error(s: str, /) -> None:
    stderr(f"[red]error:[/] {s}")


def error_with_hint(msg: str, hint_text: str, /) -> None:
    error(msg)
    stderr("")
    hint(hint_text)


def hint(s: str, /) -> None:
    stderr(f"[green]tip:[/] {s}")
