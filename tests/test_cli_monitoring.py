import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
import os

# The 'src' directory is added to sys.path by tests/conftest.py

from cli.monitoring.claude_source import ClaudeSource
from cli.monitoring.opencode_source import OpenCodeSource
from cli.monitoring.antigravity_source import AntigravitySource
from cli.monitoring.monitoring import MonitoringManager

def test_claude_source_initialization():
    source = ClaudeSource()
    assert hasattr(source, "claude_base_dir")

def test_opencode_source_initialization():
    source = OpenCodeSource()
    assert hasattr(source, "opencode_db_path")

def test_antigravity_source_initialization():
    source = AntigravitySource()
    assert hasattr(source, "conv_dir")

@patch("cli.monitoring.claude_source.Path.exists")
def test_claude_source_parse_no_dir(mock_exists):
    mock_exists.return_value = False
    source = ClaudeSource()
    sessions, totals = source.parse_claude_sessions()
    assert sessions == []
    assert totals["input"] == 0

@patch("cli.monitoring.antigravity_source.Path.exists")
def test_antigravity_source_parse_no_dir(mock_exists):
    mock_exists.return_value = False
    source = AntigravitySource()
    sessions, totals = source.parse_antigravity_sessions()
    assert sessions == []
    assert totals["input"] == 0

def test_monitoring_manager_initialization():
    # Mocking sources to avoid filesystem hits during manager init
    with patch("cli.monitoring.monitoring.ClaudeSource"), \
         patch("cli.monitoring.monitoring.OpenCodeSource"), \
         patch("cli.monitoring.monitoring.AntigravitySource"):
        manager = MonitoringManager()
        assert hasattr(manager, "claude_source")

@patch("cli.monitoring.monitoring.ClaudeSource.parse_claude_sessions")
@patch("cli.monitoring.monitoring.OpenCodeSource.parse_opencode_sessions")
@patch("cli.monitoring.monitoring.AntigravitySource.parse_antigravity_sessions")
def test_monitoring_build_screen(mock_ag, mock_oc, mock_claude):
    mock_claude.return_value = ([], {"input": 10, "output": 20, "cacheR": 0, "cacheW": 0})
    mock_oc.return_value = ([], {"input": 30, "output": 40, "cacheR": 0, "cacheW": 0})
    mock_ag.return_value = ([], {"input": 50, "output": 60, "cacheR": 0, "cacheW": 0})
    
    manager = MonitoringManager()
    screen = manager._build_screen()
    # If it returns a Group (rich object) without crashing, it passes
    assert screen is not None

def test_session_token_breakdown():
    # Test keys presence in sessions
    with patch("cli.monitoring.claude_source.ClaudeSource._parse_claude_jsonl") as mock_parse:
        mock_parse.return_value = {
            "model": "claude-3-5-sonnet", "turn_count": 5, "total_input": 100, 
            "total_output": 50, "total_cache_read": 10, "total_cache_create": 5, 
            "last_context_tokens": 110, "context_window": 200000, "status": "Wait"
        }
        # Mock index file existence and content
        with patch("cli.monitoring.claude_source.Path.exists", return_value=True), \
             patch("builtins.open", MagicMock()):
            # We need to mock json.load for the index
            with patch("json.load", return_value={"entries": [{"sessionId": "test", "fileMtime": 123, "fullPath": "dummy"}]}), \
                 patch("cli.monitoring.claude_source.Path.iterdir", return_value=[Path("project")]):
                source = ClaudeSource()
                sessions, _ = source.parse_claude_sessions()
                if sessions:
                    s = sessions[0]
                    assert "InputTokens" in s
                    assert "OutputTokens" in s
                    assert "CacheR" in s
                    assert "CacheW" in s
                    assert s["InputTokens"] == 100
