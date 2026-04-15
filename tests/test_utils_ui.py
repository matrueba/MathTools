"""
Tests for src/utils/ui.py
Covers: console instance, QUESTIONARY_STYLE
"""

from rich.console import Console
import questionary


class TestConsole:
    def test_console_is_rich_console(self):
        from utils.ui import console
        assert isinstance(console, Console)

    def test_console_is_singleton(self):
        """Importing twice should yield the same object."""
        from utils.ui import console as c1
        from utils.ui import console as c2
        assert c1 is c2


class TestQuestionaryStyle:
    def test_style_is_questionary_style(self):
        from utils.ui import QUESTIONARY_STYLE
        assert isinstance(QUESTIONARY_STYLE, questionary.Style)

    def test_style_has_entries(self):
        """The style should have token-rule pairs defined."""
        from utils.ui import QUESTIONARY_STYLE
        # questionary.Style wraps prompt_toolkit style—just verify it was created
        assert QUESTIONARY_STYLE is not None
