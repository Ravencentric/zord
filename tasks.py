from zord import Cmd, task

uv = Cmd("uv").args("run")


@task(default=True)
def check(*, fix: bool = True) -> None:

    linter = uv.args(t"ruff check").args_if(fix, "--fix")
    formatter = uv.args(t"ruff format").args_if(not fix, "--check")
    typechecker = uv.args(t"pyrefly check")

    linter.run()
    formatter.run()
    typechecker.run()
