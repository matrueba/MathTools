"""Tests for src/main.py — the `mathtools` entry point."""

from unittest.mock import patch

import pytest

import main


def test_main_serves_the_dashboard():
    with patch("main.MathToolsServer") as server:
        main.main()
    server.return_value.run_server.assert_called_once_with()


def test_unexpected_error_exits_with_status_1(caplog):
    with patch("main.MathToolsServer") as server:
        server.return_value.run_server.side_effect = RuntimeError("port in use")
        with pytest.raises(SystemExit) as exc_info:
            main.main()

    assert exc_info.value.code == 1
    assert "port in use" in caplog.text
