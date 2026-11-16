import pytest

from zord import env

NAME = "ZORD_TEST_ENV"


def test_get_and_has_read_current_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(NAME, raising=False)
    assert env.get(NAME) is None
    assert env.get(NAME, default="fallback") == "fallback"
    assert env.has(NAME) is False

    monkeypatch.setenv(NAME, "  value  ")
    assert env.get(NAME, default="fallback") == "  value  "
    assert env.has(NAME) is True

    monkeypatch.setenv(NAME, "")
    assert env.get(NAME, default="fallback") == ""
    assert env.has(NAME) is True


def test_flag_defaults_only_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(NAME, raising=False)
    assert env.flag(NAME) is False
    assert env.flag(NAME, default=True) is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", True),
        (" TRUE ", True),
        ("Yes", True),
        ("on", True),
        ("0", False),
        (" FALSE ", False),
        ("No", False),
        ("off", False),
    ],
)
def test_flag_parses_values(
    value: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(NAME, value)
    assert env.flag(NAME, default=not expected) is expected


@pytest.mark.parametrize("value", ["", " ", "maybe"])
def test_flag_rejects_invalid_values(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(NAME, value)
    with pytest.raises(ValueError, match=NAME):
        env.flag(NAME, default=True)
