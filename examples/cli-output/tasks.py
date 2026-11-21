import sys

from zord import Cmd, task

python = Cmd(sys.executable)


@task(default=True)
def live() -> None:
    """Show live output and a command that ends mid-line."""

    python.args("-c", "print('Ready')\nprint('Starting checks')").run()
    python.args("-c", "print('Working...', end='')").run()
    python.args("-c", "print('Done')").run()


@task(default=True)
def captured() -> None:
    """Show a capture status and use the returned output."""

    version = python.args("-c", "print('0.1.0')").stdout()
    print(f"Version from captured stdout = {version}")


@task
def fail_live() -> None:
    """Show a live command's stderr and the task failure."""

    python.args("-c", "raise SystemExit('A live command failed')").run()


@task
def fail_captured() -> None:
    """Show a captured command's nonzero exit status."""

    python.args("-c", "raise SystemExit(7)").capture()
