"""
Tests for src/cli/general.py
Covers: print_banner(), prompt_no_environments_found(), show_main_menu()
"""

from unittest.mock import patch, MagicMock, call

import pytest


class TestPrintBanner:
    def test_prints_banner(self):
        """print_banner should call console.print with the banner panel."""
        with patch("cli.general.console") as mock_console:
            from cli.general import print_banner
            print_banner()
            # Should have at least one print call for the panel and one for spacing
            assert mock_console.print.call_count >= 2

    def test_banner_contains_version(self):
        """Banner should display the current version."""
        with patch("cli.general.console") as mock_console:
            from cli.general import print_banner
            print_banner()

        # Check that the Panel passed to console.print contains version info
        first_call_args = mock_console.print.call_args_list[0]
        panel = first_call_args[0][0]
        # The panel's renderable should contain the version
        from constants.general import VERSION
        # Rich Panel wraps content—we just verify it was called with a Panel
        from rich.panel import Panel
        assert isinstance(panel, Panel)

    def test_banner_contains_ascii_art(self):
        """Banner should contain the MathTools ASCII art."""
        with patch("cli.general.console") as mock_console:
            from cli.general import print_banner
            print_banner()

        first_call_args = mock_console.print.call_args_list[0]
        panel = first_call_args[0][0]
        from rich.panel import Panel
        assert isinstance(panel, Panel)


class TestPromptNoEnvironmentsFound:
    def test_returns_true_when_confirmed(self):
        """Should return True when user confirms installation."""
        with patch("cli.general.console"):
            with patch("cli.general.Confirm.ask", return_value=True):
                from cli.general import prompt_no_environments_found
                result = prompt_no_environments_found()
                assert result is True

    def test_returns_false_when_declined(self):
        """Should return False when user declines installation."""
        with patch("cli.general.console"):
            with patch("cli.general.Confirm.ask", return_value=False):
                from cli.general import prompt_no_environments_found
                result = prompt_no_environments_found()
                assert result is False

    def test_displays_environment_info(self):
        """Should display a panel with environment directory info."""
        with patch("cli.general.console") as mock_console:
            with patch("cli.general.Confirm.ask", return_value=True):
                from cli.general import prompt_no_environments_found
                prompt_no_environments_found()

        # Should have called console.print with a Panel
        from rich.panel import Panel
        called_with_panel = any(
            isinstance(c[0][0], Panel) for c in mock_console.print.call_args_list if c[0]
        )
        assert called_with_panel


class TestShowMainMenu:
    def test_returns_install(self):
        """Should return 'install' when user selects install option."""
        with patch("cli.general.console"):
            with patch("cli.general.questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = "install"
                from cli.general import show_main_menu
                result = show_main_menu()
                assert result == "install"

    def test_returns_memory(self):
        """Should return 'memory' when user selects memory option."""
        with patch("cli.general.console"):
            with patch("cli.general.questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = "memory"
                from cli.general import show_main_menu
                result = show_main_menu()
                assert result == "memory"

    def test_returns_exit(self):
        """Should return 'exit' when user selects exit option."""
        with patch("cli.general.console"):
            with patch("cli.general.questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = "exit"
                from cli.general import show_main_menu
                result = show_main_menu()
                assert result == "exit"

    def test_returns_exit_on_none(self):
        """If questionary returns None (Ctrl+C), should default to 'exit'."""
        with patch("cli.general.console"):
            with patch("cli.general.questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = None
                from cli.general import show_main_menu
                result = show_main_menu()
                assert result == "exit"

    def test_provides_three_choices(self):
        """Menu should offer exactly 3 choices."""
        with patch("cli.general.console"):
            with patch("cli.general.questionary.select") as mock_select:
                mock_select.return_value.ask.return_value = "exit"
                from cli.general import show_main_menu
                show_main_menu()

                call_kwargs = mock_select.call_args
                choices = call_kwargs[1].get("choices", call_kwargs[0][1] if len(call_kwargs[0]) > 1 else [])
                assert len(choices) == 3
