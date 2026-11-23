from __future__ import annotations

import linecache
import os
import signal
import subprocess
import sys
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from textwrap import indent
from typing import Final

from .. import annotation, console
from ..errors import (
    BooleanOptionConflictError,
    DuplicateTaskIdError,
    InvalidTaskIdError,
    MissingDefaultError,
    MixedVariadicSignatureError,
    PositionalBoolError,
    ReservedOptionError,
    SignatureInspectionError,
    TaskDefinitionError,
    TaskError,
    UnsupportedAnnotationError,
    UnsupportedTaskFunctionError,
    VarKeywordError,
    ZordError,
)
from ..model import Task

STDLIB: Final = sys.stdlib_module_names | {"zord"}


def relpath(filename: str, /) -> str:
    try:
        return os.path.relpath(filename)
    except ValueError:
        # relpath cannot cross drive or UNC mount boundaries on Windows.
        return filename


def width(text: str, /) -> int:
    """
    len() returns unicode codepoints which doesn't work out for us.

    ```
    len("🚀🚀🚀abcdef") -> 9
    len("___abcdef") -> 9
    ```
    As you can see, len() returns 9 for both but the emojis take
    twice as much "display" width compared to an ascii character.
    """
    text = text.expandtabs()
    if text.isascii():
        return len(text)

    from unicodedata import category, east_asian_width

    return sum(
        2 if east_asian_width(char) in {"W", "F"} else 1
        for char in text
        if category(char) not in {"Mn", "Me", "Cf"}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceLocation:
    filename: str
    lineno: int
    source: str
    start: int | None
    end: int | None
    function: str | None = None

    @property
    def padding(self) -> str:
        return " " * len(str(self.lineno))

    def render(self) -> str:
        """
        Render a rustc-like diagnostic.

          --> tasks.py:79:9
           |
        79 |         raise RuntimeError("invalid deployment settings")
           |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ in failure()

        """

        # Nothing to render if the line is empty (which is possible in
        # some cases like exec(compile(...)))
        line = self.source.partition("\n")[0].removesuffix("\r")
        if not line.strip():
            return ""

        lineno = self.lineno
        start = self.start
        padding = self.padding

        # +1 because editors expect 1-based index when it comes to code location.
        col = f":{start + 1}" if start is not None else ""
        arrow = (
            f"{padding}{console.render('[cyan]-->[/]')} "
            f"{relpath(self.filename)}:{lineno}{col}"
        )

        # The "in func()" part, if any.
        context = (
            console.render(f" in [magenta]{self.function}()[/]")
            if self.function
            else ""
        )

        margin = console.render(f"{padding} [cyan]|[/]")
        excerpt = f"{console.render(f'[cyan]{lineno} |[/]')} {line.expandtabs()}"

        # Python may omit columns with PYTHONNODEBUGRANGES (Why is this a thing?)
        # https://docs.python.org/3/using/cmdline.html#envvar-PYTHONNODEBUGRANGES
        if start is None or not 0 <= start <= len(line):
            return f"{arrow}{context}\n{margin}\n{excerpt}"

        # len() is not enough when unicode gets involved, like emojis.
        left = width(line[:start])
        right = left if self.end is None else width(line[: self.end])
        # A point location still needs one caret.
        carets = "^" * max(1, right - left)
        underline = (
            f"{margin} {' ' * left}{console.render(f'[red]{carets}[/]')}{context}"
        )
        return f"{arrow}\n{margin}\n{excerpt}\n{underline}"


def charindex(source: str, byte_offset: int | None, /) -> int | None:
    """Convert a traceback's UTF-8 byte offset to an index for slicing the source."""
    if source and byte_offset is not None:
        return len(
            source.encode("utf-8")[:byte_offset].decode("utf-8", errors="ignore")
        )
    return byte_offset


def location_of(exc: BaseException) -> SourceLocation | None:
    # Parsing can fail before Python executes the affected file. Use the parser's
    # source and turn its one-based offsets into string indexes.
    if isinstance(exc, SyntaxError) and exc.filename and exc.lineno:
        start = exc.offset - 1 if exc.offset else None

        # Check if the error spans a single line.
        # We only bother underlining if it's a single line.
        # if the error is multiline then we just mark the start.
        end = (
            exc.end_offset - 1
            if exc.end_lineno == exc.lineno and exc.end_offset
            else None
        )
        return SourceLocation(
            filename=exc.filename,
            lineno=exc.lineno,
            source=exc.text or "",
            start=start,
            end=end,
        )

    # Walk from outermost call to innermost.
    # Prefer the deepest frame outside stdlib or zord itself.
    preferred = last = None
    tb = exc.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        # Skip pseudo-filenames such as <string> so the location can point to a file.
        if not frame.f_code.co_filename.startswith("<"):
            last = tb
            package = str(frame.f_globals.get("__name__", "")).partition(".")[0]
            if package not in STDLIB:
                preferred = tb
        tb = tb.tb_next

    # An exception attached as a cause may never have been raised and have no frames.
    if (location := preferred or last) is None:
        return None

    (summary,) = traceback.extract_tb(location, limit=1)
    lineno = summary.lineno or location.tb_lineno
    # Read the original indentation because the offsets include it.
    source = linecache.getline(summary.filename, lineno, location.tb_frame.f_globals)
    # Traceback offsets count UTF-8 bytes. Convert to string indexes, using the
    # end offset only when it points into the line we show.
    end = summary.end_colno if summary.end_lineno == lineno else None
    return SourceLocation(
        filename=summary.filename,
        lineno=lineno,
        source=source,
        start=charindex(source, summary.colno),
        end=charindex(source, end),
        function=summary.name,
    )


def cmderr(error: subprocess.CalledProcessError) -> str:
    """Describe a command that exited or was terminated by a signal."""
    command: object = error.cmd

    if isinstance(command, (str, bytes)):
        # A command string may contain shell syntax instead of an executable path.
        if len(command.split(maxsplit=1)) > 1:
            command = None
    elif isinstance(command, Sequence):
        command = command[0] if command else None

    name = "command"
    if isinstance(command, (str, bytes, os.PathLike)):
        try:
            path = os.fsdecode(command)
        except Exception:  # noqa: BLE001 - We don't want fail trying to show an error lol
            path = ""

        name = os.path.basename(path) or name

    if error.returncode >= 0:
        return f"{name} exited with code {error.returncode}"

    # Subprocess uses negative return codes for signal termination.
    number = -error.returncode
    try:
        reason = signal.Signals(number).name
    except ValueError:
        reason = f"signal {number}"

    return f"{name} terminated by {reason}"


def report(error: ZordError) -> None:
    """Print the exception chain to stderr."""
    causes = error.causes()
    if not causes:
        return

    blocks = []
    for i, cause in enumerate(causes):
        prefix = f"    {i}: "
        stderr: str | bytes | None = None

        if isinstance(cause, subprocess.CalledProcessError):
            block = prefix + cmderr(cause)
            stderr = cause.stderr
        else:
            name = console.render(f"[magenta]{type(cause).__name__}[/]")
            text = cause.msg if isinstance(cause, SyntaxError) else str(cause)

            block = prefix + name
            if text:
                block += f": {text}"

        location = location_of(cause)
        excerpt = location.render() if location else ""
        if excerpt:
            block += "\n\n" + indent(excerpt, "    ")

        # Python's subprocess API can capture stderr as either bytes or text.
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stderr = "\n".join((stderr or "").splitlines()).rstrip("\n")

        if stderr:
            padding = location.padding if location and excerpt else " "
            arrow = console.render(f"{padding}[cyan]-->[/]")
            margin = console.render(f"{padding} [cyan]|[/]")
            lines = "\n".join(
                f"{margin} {line}" if line else margin for line in stderr.split("\n")
            )
            block += "\n\n" + indent(f"{arrow} stderr\n{margin}\n{lines}", "    ")

        blocks.append(block)

    heading = console.render("[yellow]caused by:[/]")
    console.stderr(f"\n{heading}\n" + "\n\n".join(blocks), markup=False)


def failure(message: str, /) -> None:
    sys.stdout.flush()
    console.stderr("")
    console.stderr(console.heading("zord"), markup=False)
    console.error(message)


def run(first: Task, /, *rest: Task) -> int:
    tasks = (first, *rest)
    passed = 0
    try:
        for i, task in enumerate(tasks):
            if i:
                console.stderr("")
            console.stderr(console.heading(task.id), markup=False)
            task.call()
            sys.stdout.flush()
            passed += 1

    except TaskError as error:
        failure(f"{error.id} failed")
        if skipped := tasks[passed + 1 :]:
            names = ", ".join(task.id for task in skipped)
            console.stderr(f"[yellow]skipped:[/] {names}")
        report(error)
        return 1

    except KeyboardInterrupt:
        failure("interrupted")
        return 130

    return 0


def invoke(task: Task, /, *args: object, **kwargs: object) -> int:
    try:
        console.stderr(console.heading(task.id), markup=False)
        task.call(*args, **kwargs)
        sys.stdout.flush()

    except TaskError as error:
        failure(f"{error.id} failed")
        report(error)
        return 1

    except KeyboardInterrupt:
        failure("interrupted")
        return 130

    return 0


def show(tasks: Sequence[Task], taskfile: str, /) -> None:
    total = len(tasks)
    label = "task" if total == 1 else "tasks"
    legend = " (* = default)" if tasks else ""
    prefix = "──"

    # Workaround for Windows where the above prefix
    # results in a unicode error.
    try:
        prefix.encode(sys.stdout.encoding or "utf-8")
    except UnicodeEncodeError:
        prefix = "--"

    header = f"[dim]{prefix}[/] {taskfile}: [dim]{total} {label}{legend}[/]"
    console.stdout(header)

    if not tasks:
        return

    console.stdout("")
    width = max(len(task.id) for task in tasks) + 1

    for task in tasks:
        star = "[yellow]*[/]" if task.default else " "
        description = task.description.splitlines()[0] if task.description else ""
        desc = f"  [dim]{description}[/]" if description else ""
        id = task.id.ljust(width) if description else task.id
        console.stdout(f"  {star} [cyan]{id}[/]{desc}")


def diagnostic_for(error: TaskDefinitionError) -> tuple[str, str]:

    match error:
        case SignatureInspectionError(id=id, source=source):
            message = f": {source}" if str(source) else ""
            return (
                f"could not inspect task [cyan]{id!r}[/] signature",
                f"signature inspection raised [magenta]{type(source).__name__}[/]{message}",
            )

        case UnsupportedTaskFunctionError(id=id, kind=kind):
            return (
                f"task [cyan]{id!r}[/] is an unsupported [magenta]{kind} function[/]",
                "wrap it in a regular task that runs or consumes it explicitly",
            )

        case DuplicateTaskIdError(id=id):
            return (
                f"duplicate task id [yellow]{id!r}[/]",
                "two functions resolved to the same id; use [magenta]@task(name=...)[/] to disambiguate",
            )

        case VarKeywordError(id=id, param=param):
            return (
                f"task [cyan]{id!r}[/] cannot use [magenta]**{param}[/]",
                "variadic keyword args are not supported; list parameters explicitly",
            )

        case MissingDefaultError(id=id, param=param):
            return (
                f"task [cyan]{id!r}[/] has parameter [magenta]{param!r}[/] without a default",
                "all task parameters must have default values",
            )

        case PositionalBoolError(id=id, param=param):
            return (
                f"task [cyan]{id!r}[/] has positional bool parameter [magenta]{param!r}[/]",
                f"bool parameters must be keyword-only (use [magenta]'*, {param}: bool = ...'[/])",
            )

        case UnsupportedAnnotationError(annotation=ann, id=id, param=param):
            supported = ", ".join(
                f"[magenta]{type.__name__}[/]" for type in annotation.SCALARS
            )
            return (
                f"task [cyan]{id!r}[/] parameter [magenta]{param!r}[/]: unsupported annotation [magenta]{ann!r}[/]",
                f"supported types: {supported}",
            )

        case MixedVariadicSignatureError(id=id, param=param):
            return (
                f"task [cyan]{id!r}[/] cannot mix [magenta]*{param}[/] with other parameters",
                f"remove the other parameters or replace [magenta]*{param}[/] with explicit parameters",
            )

        case ReservedOptionError(id=id, option=option, param=param):
            return (
                f"task [cyan]{id!r}[/] parameter [magenta]{param!r}[/] conflicts with reserved option [yellow]{option!r}[/]",
                f"rename the parameter; [yellow]{option}[/] is reserved for task help",
            )

        case BooleanOptionConflictError(
            id=id,
            option=option,
            param=param,
            conflict=conflict,
        ):
            return (
                f"task [cyan]{id!r}[/] parameters [magenta]{param!r}[/] and [magenta]{conflict!r}[/] both define option [yellow]{option!r}[/]",
                "rename one parameter so its command-line option is unique",
            )

        case InvalidTaskIdError(ids=ids):
            prefix = "ids" if len(ids) > 1 else "id"
            quoted = ", ".join(f"[yellow]{n!r}[/]" for n in ids)
            return (
                f"invalid task {prefix} {quoted}",
                (
                    "ids must start with a letter, end with a letter or number, "
                    "and contain only printable non-whitespace characters"
                ),
            )

        case _:
            raise AssertionError(
                f"unhandled TaskDefinitionError: {type(error).__name__}: {error}"
            )
