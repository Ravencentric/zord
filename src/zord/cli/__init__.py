from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from .. import console
from ..errors import (
    InvalidTaskIdError,
    TaskDefinitionError,
    TaskFileNotFoundError,
    UndefinedTaskIdError,
    ZordError,
)
from ..model import TaskId
from ..registry import TaskRegistry
from .fmt import causes_of, diagnostic_for, invoke, run, show
from .parser import (
    TASKFILE,
    Command,
    Invoke,
    RunSelected,
    TaskParser,
    ZordFlag,
    command,
)


def missing_separator_hint(cmd: Command, tasks: Sequence[TaskId], /) -> str | None:
    match cmd:
        case RunSelected(names=[first, *rest]) if rest:
            first = TaskId.new(first)
            rest = (TaskId.new(task) for task in rest)
            # A valid first task followed only by unknown or invalid names often
            # means the user omitted the argument separator.
            if (
                first is not None
                and first in tasks
                and all(task is None or task not in tasks for task in rest)
            ):
                return (
                    f"if the values after {first!r} are arguments, use '--': "
                    f"[cyan]zord {first} -- <arg> ...[/]"
                )
        case _:
            return None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return cli(argv)
    except KeyboardInterrupt:
        console.error("interrupted")
        return 130


def cli(argv: Sequence[str] | None = None) -> int:
    cmd = command(sys.argv[1:] if argv is None else argv)

    try:
        registry = TaskRegistry.load(Path.cwd() / TASKFILE)
    except TaskFileNotFoundError as error:
        console.error_with_hint(
            error.msg,
            "create [cyan]tasks.py[/] here, or run zord from the project root",
        )
        return 2

    except TaskDefinitionError as error:
        err, hint = diagnostic_for(error)
        console.error_with_hint(err, hint)
        return 1

    except ZordError as error:
        console.error(error.msg)
        if causes := causes_of(error):
            console.stderr(causes)
        return 1

    return execute(cmd, registry)


def execute(cmd: Command, registry: TaskRegistry, /) -> int:
    try:
        match cmd:
            case ZordFlag.DEFAULT:
                tasks = registry.default()
                if not tasks:
                    console.error("no default tasks")
                    return 2
                first, *rest = tasks
                return run(first, *rest)

            case RunSelected(names=names):
                tasks = registry.select(names)
                if not tasks:
                    console.error("no tasks selected")
                    return 2
                first, *rest = tasks
                return run(first, *rest)

            case ZordFlag.LIST:
                show(registry.all(), registry.file.name)
                return 0

            case Invoke(name=name, argv=argv):
                task = registry.get(name)
                pos, kw = TaskParser(task).parse(argv)
                return invoke(task, *pos, **kw)

    # Raised by registry.select() or registry.get()
    except InvalidTaskIdError as error:
        err, hint = diagnostic_for(error)
        console.error_with_hint(err, hint)
        if hint := missing_separator_hint(cmd, registry.ids()):
            console.stderr("")
            console.hint(hint)
        return 2

    # Raised by registry.select() or registry.get()
    except UndefinedTaskIdError as error:
        label = "task" if len(error.ids) == 1 else "tasks"
        names = ", ".join(f"[yellow]{n!r}[/]" for n in error.ids)
        console.error(f"unknown {label} {names}")

        available = registry.ids()
        hints = error.suggest(available)

        if hints:
            console.stderr("")
            suggested = ", ".join(f"[cyan]{h}[/]" for h in hints)
            console.hint(f"did you mean {suggested}?")

        elif hint := missing_separator_hint(cmd, available):
            console.stderr("")
            console.hint(hint)

        elif available:
            console.stderr("")
            avail = ", ".join(f"[cyan]{a!r}[/]" for a in available)
            console.hint(f"available tasks: {avail}")

        return 2

    except ZordError as error:
        console.error(str(error))
        if causes := causes_of(error):
            console.stderr(causes)
        return 1
