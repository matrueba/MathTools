import pytest

from unittest.mock import MagicMock, patch
from pathlib import Path
import sys
import os
import time


# The 'src' directory is added to sys.path by tests/conftest.py

from cli.monitoring.claude_source import ClaudeSource
from cli.monitoring.opencode_source import OpenCodeSource
from cli.monitoring.antigravity_source import AntigravitySource
from cli.monitoring.gemini_source import GeminiSource
from cli.monitoring.monitoring import MonitoringManager
from cli.monitoring.extended import render_extended_session
from rich.console import Group

def test_claude_source_initialization():
    source = ClaudeSource()
    assert hasattr(source, "claude_base_dir")

def test_opencode_source_initialization():
    source = OpenCodeSource()
    assert hasattr(source, "opencode_db_path")

def test_antigravity_source_initialization():
    source = AntigravitySource()
    assert hasattr(source, "conv_dir")

def test_gemini_source_initialization():
    source = GeminiSource()
    assert hasattr(source, "tmp_dir")

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

@patch("cli.monitoring.gemini_source.Path.exists")
def test_gemini_source_parse_no_dir(mock_exists):
    mock_exists.return_value = False
    source = GeminiSource()
    sessions, totals = source.parse_gemini_sessions()
    assert sessions == []
    assert totals["input"] == 0

def test_monitoring_manager_initialization():
    # Mocking sources to avoid filesystem hits during manager init
    with patch("cli.monitoring.monitoring.ClaudeSource"), \
         patch("cli.monitoring.monitoring.OpenCodeSource"), \
         patch("cli.monitoring.monitoring.AntigravitySource"), \
         patch("cli.monitoring.monitoring.GeminiSource"):
        manager = MonitoringManager()
        assert hasattr(manager, "claude_source")
        assert hasattr(manager, "gemini_source")

@patch("cli.monitoring.monitoring.ClaudeSource.parse_claude_sessions")
@patch("cli.monitoring.monitoring.OpenCodeSource.parse_opencode_sessions")
@patch("cli.monitoring.monitoring.AntigravitySource.parse_antigravity_sessions")
@patch("cli.monitoring.monitoring.GeminiSource.parse_gemini_sessions")
@patch("os.get_terminal_size")
def test_monitoring_build_screen(mock_size, mock_ge, mock_ag, mock_oc, mock_claude):
    mock_size.return_value = MagicMock(lines=24, columns=80)
    mock_claude.return_value = ([], {"input": 10, "output": 20, "cacheR": 0, "cacheW": 0})
    mock_oc.return_value = ([], {"input": 30, "output": 40, "cacheR": 0, "cacheW": 0})
    mock_ag.return_value = ([], {"input": 50, "output": 60, "cacheR": 0, "cacheW": 0})
    mock_ge.return_value = ([], {"input": 70, "output": 80, "cacheR": 0, "cacheW": 0})
    
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

def test_render_extended_session_logic():
    """Test the extended session rendering with various data states."""
    # 1. No session
    assert isinstance(render_extended_session(None), Group)
    
    # 2. Complete session
    session = {
        "SessionId": "123456789012345",
        "ProjectPath": "/root/mathtools",
        "AI": "Antigravity",
        "Status": "Work",
        "Summary": "Testing extended view",
        "PIDs": [9999],
        "Subagents": [{"status": "work", "label": "Subtask 1"}],
        "InputTokens": 1500,
        "OutputTokens": 800,
        "CacheR": 200,
        "CacheW": 100,
        "ContextWindow": 128000,
        "LastContext": 64000,
        "Model": "gemini-1.5-pro",
        "mtime": 1713650000,
        "TurnCount": 12
    }
    
    with patch("subprocess.check_output") as mock_ps:
        mock_ps.return_value = b"python 2.5 102400"
        result = render_extended_session(session)
        assert isinstance(result, Group)

def test_render_extended_session_minimal_data():
    """Test rendering with minimal required session keys."""
    session = {
        "SessionId": "short",
        "PIDs": [],
        "Subagents": []
    }
    result = render_extended_session(session)
    assert isinstance(result, Group)

def test_gemini_source_parsing_logic():
    """Test GeminiSource session parsing with mocked messages."""
    with patch("cli.monitoring.gemini_source.Path.exists", return_value=True), \
         patch("cli.monitoring.gemini_source.Path.iterdir") as mock_iter:
        
        # Mock project directory and chats directory
        mock_proj = MagicMock(spec=Path)
        mock_proj.is_dir.return_value = True
        mock_proj.name = "test-project"
        
        mock_chats = MagicMock(spec=Path)
        mock_chats.exists.return_value = True
        
        mock_proj.__truediv__.return_value = mock_chats
        mock_iter.return_value = [mock_proj]
        
        # Mock session file
        mock_session_file = MagicMock(spec=Path)
        mock_session_file.stem = "session-12345"
        mock_chats.glob.return_value = [mock_session_file]
        
        session_data = {
            "messages": [
                {
                    "type": "user",
                    "content": [{"text": "Hello Gemini"}]
                },
                {
                    "type": "gemini",
                    "model": "gemini-3-flash",
                    "tokens": {"input": 100, "output": 50, "cached": 10},
                    "thoughts": [{"subject": "Thinking", "description": "Processing request"}]
                }
            ]
        }
        
        with patch("builtins.open", MagicMock()), \
             patch("json.load", return_value=session_data), \
             patch("os.path.getmtime", return_value=time.time()):
            source = GeminiSource()
            sessions, totals = source.parse_gemini_sessions()
            
            assert len(sessions) == 1
            assert sessions[0]["Project"] == "test-project"
            assert sessions[0]["Summary"] == "Thinking"
            assert sessions[0]["TotalTokens"] == 160
            assert totals["input"] == 100
