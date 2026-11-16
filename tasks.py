from zord import Cmd, task

uv = Cmd("uv").args("run")


@task(default=True)
def check(*, fix: bool = True) -> None:

    linter = uv.args(t"ruff check")
    formatter = uv.args(t"ruff format")
    typechecker = uv.args(t"pyrefly check")

    if fix:
        linter += "--fix"
    else:
        formatter += "--check"

    linter.run()
    formatter.run()
    typechecker.run()
