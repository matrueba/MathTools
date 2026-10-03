"""
Tests for src/main.py
Covers: main() function, all branches and exception handling
"""

import sys
from unittest.mock import patch, MagicMock

import pytest
import requests


class TestMain:
    def test_no_envs_user_declines(self):
        """When no envs found and user declines, should exit 0."""
        with patch("main.print_banner"):
            with patch("main.detect_environments", return_value=[]):
                with patch("main.prompt_no_environments_found", return_value=False):
                    with patch("main.console") as mock_console:
                        from main import main
                        with pytest.raises(SystemExit) as exc_info:
                            main(["--cli"])
                        assert exc_info.value.code == 0

    def test_no_envs_user_accepts(self):
        """When no envs found and user accepts, should run installer then exit."""
        mock_installer = MagicMock()

        with patch("main.print_banner"):
            with patch("main.detect_environments", return_value=[]):
                with patch("main.prompt_no_environments_found", return_value=True):
                    with patch("main.FrameworkInstaller", return_value=mock_installer):
                        with patch("main.MemoryManager"):
                            from main import main
                            with pytest.raises(SystemExit) as exc_info:
                                main(["--cli"])
                            assert exc_info.value.code == 0
                            mock_installer.run_installer.assert_called_once()

    def test_envs_found_install_action(self):
        """When environments exist and user picks install, should run installer."""
        mock_installer = MagicMock()
        found = [("gemini", "Gemini CLI", "local")]

        with patch("main.print_banner"):
            with patch("main.detect_environments", return_value=found):
                with patch("main.show_main_menu", return_value="install"):
                    with patch("main.FrameworkInstaller", return_value=mock_installer):
                        with patch("main.MemoryManager"):
                            with patch("main.console"):
                                from main import main
                                main(["--cli"])
                                mock_installer.run_installer.assert_called_once()

    def test_envs_found_memory_action(self):
        """When environments exist and user picks memory, should run memory manager."""
        mock_memory = MagicMock()
        found = [("gemini", "Gemini CLI", "local")]

        with patch("main.print_banner"):
            with patch("main.detect_environments", return_value=found):
                with patch("main.show_main_menu", return_value="memory"):
                    with patch("main.FrameworkInstaller"):
                        with patch("main.MemoryManager", return_value=mock_memory):
                            with patch("main.console"):
                                from main import main
                                main(["--cli"])
                                mock_memory.run_manage_memory.assert_called_once()

    def test_envs_found_exit_action(self):
        """When environments exist and user picks exit, should print goodbye."""
        found = [("gemini", "Gemini CLI", "local")]

        with patch("main.print_banner"):
            with patch("main.detect_environments", return_value=found):
                with patch("main.show_main_menu", return_value="exit"):
                    with patch("main.FrameworkInstaller"):
                        with patch("main.MemoryManager"):
                            with patch("main.console") as mock_console:
                                from main import main
                                main(["--cli"])
                                # Should print goodbye
                                calls = [str(c) for c in mock_console.print.call_args_list]
                                assert any("Goodbye" in c for c in calls)

    def test_network_error_handling(self):
        """Should handle RequestException and exit 1."""
        with patch("main.print_banner", side_effect=requests.RequestException("timeout")):
            with patch("main.FrameworkInstaller"):
                with patch("main.MemoryManager"):
                    with patch("main.console"):
                        from main import main
                        with pytest.raises(SystemExit) as exc_info:
                            main(["--cli"])
                        assert exc_info.value.code == 1

    def test_keyboard_interrupt_handling(self):
        """Should handle KeyboardInterrupt and exit 130."""
        with patch("main.print_banner", side_effect=KeyboardInterrupt):
            with patch("main.FrameworkInstaller"):
                with patch("main.MemoryManager"):
                    with patch("main.console"):
                        from main import main
                        with pytest.raises(SystemExit) as exc_info:
                            main(["--cli"])
                        assert exc_info.value.code == 130

    def test_generic_exception_handling(self):
        """Should handle unexpected exceptions and exit 1."""
        with patch("main.print_banner", side_effect=RuntimeError("boom")):
            with patch("main.FrameworkInstaller"):
                with patch("main.MemoryManager"):
                    with patch("main.console"):
                        from main import main
                        with pytest.raises(SystemExit) as exc_info:
                            main(["--cli"])
                        assert exc_info.value.code == 1

    def test_displays_detected_environments_table(self):
        """When environments are found, should display them in a table."""
        found = [
            ("gemini", "Gemini CLI", "local"),
            ("agents", "Standard IDE agents", "global"),
        ]

        with patch("main.print_banner"):
            with patch("main.detect_environments", return_value=found):
                with patch("main.show_main_menu", return_value="exit"):
                    with patch("main.FrameworkInstaller"):
                        with patch("main.MemoryManager"):
                            with patch("main.console") as mock_console:
                                from main import main
                                main(["--cli"])

                            # Should have printed a Table
                            from rich.table import Table
                            table_calls = [
                                c for c in mock_console.print.call_args_list
                                if c[0] and isinstance(c[0][0], Table)
                            ]
                            assert len(table_calls) >= 1


class TestModeSelection:
    """`mathtools` serves the web dashboard; `mathtools --cli` opens the TUI."""

    def test_defaults_to_web(self):
        with patch("main.run_web") as mock_web:
            with patch("main.run_cli") as mock_cli:
                from main import main
                main([])

                mock_web.assert_called_once()
                mock_cli.assert_not_called()

    def test_cli_flag_selects_the_terminal_ui(self):
        with patch("main.run_web") as mock_web:
            with patch("main.run_cli") as mock_cli:
                from main import main
                main(["--cli"])

                mock_cli.assert_called_once()
                mock_web.assert_not_called()

    def test_no_argv_reads_sys_argv(self):
        """The console entry point calls main() with no arguments."""
        with patch("sys.argv", ["mathtools", "--cli"]):
            with patch("main.run_web") as mock_web:
                with patch("main.run_cli") as mock_cli:
                    from main import main
                    main()

                    mock_cli.assert_called_once()
                    mock_web.assert_not_called()

    def test_parse_args_defaults_to_web(self):
        from main import parse_args
        assert parse_args([]).cli is False
        assert parse_args(["--cli"]).cli is True

    def test_help_exits_zero(self):
        from main import parse_args
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_unknown_argument_is_rejected(self):
        from main import parse_args
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--nope"])
        assert exc_info.value.code == 2

    def test_run_web_launches_the_dashboard(self):
        mock_dashboard = MagicMock()
        with patch("main.print_banner"):
            with patch("main.WebDashboard", return_value=mock_dashboard):
                from main import run_web
                run_web()

                mock_dashboard.run_web_dashboard.assert_called_once()

    def test_web_mode_errors_are_handled(self):
        """The shared error handling must wrap web mode too, not just the CLI."""
        with patch("main.run_web", side_effect=KeyboardInterrupt):
            with patch("main.console"):
                from main import main
                with pytest.raises(SystemExit) as exc_info:
                    main([])
                assert exc_info.value.code == 130
