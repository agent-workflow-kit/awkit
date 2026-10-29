import pytest

from awkit import __version__
from awkit.cli import main


def test_version_exits_zero_and_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"awkit {__version__}"


def test_no_args_returns_usage() -> None:
    assert main([]) == 2
