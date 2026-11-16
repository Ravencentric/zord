from zord import Cmd, env, task

uv = Cmd("uv").args("run")


@task(default=True)
def check(*, fix: bool = True) -> None:
    """Run static analyzers"""

    uv.args(t"ruff check").args_if(fix, "--fix").run()
    uv.args(t"ruff format").args_if(not fix, "--check").run()
    uv.args(t"pyrefly check").run()


@task(default=True)
def test(*, fix: bool = True) -> None:
    """Run pytest"""

    uv.args(t"pytest").args_if(env.flag("CI"), "-vv").run()
