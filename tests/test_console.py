import os

from pytest import CaptureFixture, MonkeyPatch

from zord import console
from zord.console import Style


def test_style() -> None:
    assert console.Style.RESET.marker == "[/]"
    assert console.Style.RESET.to_ansi() == "\033[0m"


def test_stdout_stderr(capsys: CaptureFixture[str]) -> None:
    console.stdout("Hello from stdout")
    console.stderr("Hello from stderr")
    out, err = capsys.readouterr()
    assert out == "Hello from stdout\n"
    assert err == "Hello from stderr\n"


def test_render(monkeypatch: MonkeyPatch) -> None:
    text = "[cyan]cyan[/] [red]red[/] [dim]dim[/] normal"
    plain = "cyan red dim normal"
    rendered = (
        f"{Style.CYAN}cyan{Style.RESET} "
        f"{Style.RED}red{Style.RESET} "
        f"{Style.DIM}dim{Style.RESET} "
        "normal"
    )

    monkeypatch.setattr(console, "can_colorize", lambda: True)
    assert console.can_colorize() is True
    assert console.render(text) == rendered

    monkeypatch.setattr(console, "can_colorize", lambda: False)
    assert console.can_colorize() is False
    assert console.render(text) == plain


def test_heading_command_and_status_styles(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "can_colorize", lambda: True)

    console.heading("check")
    console.command("my tool", "[red]", end="  ")
    console.status(0)
    console.command("tool", end="  ")
    console.status(7)

    executable = '"my tool"' if os.name == "nt" else "'my tool'"
    argument = "[red]" if os.name == "nt" else "'[red]'"
    prompt = f"{Style.YELLOW}${Style.RESET}"
    assert capsys.readouterr().err == (
        f"{Style.DIM}──{Style.RESET} {Style.CYAN}check{Style.RESET}\n"
        f"\n{prompt} {Style.MAGENTA}{executable}{Style.RESET} {argument}"
        f"  {Style.GREEN}✓{Style.RESET} {Style.DIM}(captured){Style.RESET}\n"
        f"\n{prompt} {Style.MAGENTA}tool{Style.RESET}"
        f"  {Style.RED}✗{Style.RESET} {Style.DIM}(exit 7){Style.RESET}\n"
    )
