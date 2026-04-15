"""
Tests for src/utils/common.py
Covers: detect_environments()
"""

import os
import pytest
from unittest.mock import patch


class TestDetectEnvironments:
    def test_no_environments_found(self, tmp_dir):
        """When no AI framework dirs exist locally or globally, return empty list."""
        from utils.common import detect_environments

        # Mock expanduser to return paths inside tmp_dir so real global dirs are ignored
        def mock_expanduser(path):
            return str(tmp_dir / "fake_home" / path.lstrip("~/"))

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()
        assert result == []

    def test_local_environment_detected(self, tmp_dir):
        """A local .gemini directory should be detected."""
        from utils.common import detect_environments
        (tmp_dir / ".gemini").mkdir()

        def mock_expanduser(path):
            return str(tmp_dir / "fake_home" / path.lstrip("~/"))

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()
        keys = [r[0] for r in result]
        assert "gemini" in keys

    def test_local_scope_string(self, tmp_dir):
        """Scope should include 'local' for local directories."""
        from utils.common import detect_environments
        (tmp_dir / ".gemini").mkdir()

        def mock_expanduser(path):
            return str(tmp_dir / "fake_home" / path.lstrip("~/"))

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()
        gemini = [r for r in result if r[0] == "gemini"][0]
        assert "local" in gemini[2]

    def test_global_environment_detected(self, tmp_dir):
        """A global directory should be detected."""
        from utils.common import detect_environments

        global_dir = tmp_dir / "fake_home_gemini"
        global_dir.mkdir()

        _real_isdir = os.path.isdir

        def mock_expanduser(path):
            # Route all global paths to the same fake dir
            return str(global_dir)

        def mock_isdir(path):
            # Use the real isdir to avoid recursion
            return _real_isdir(path)

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()

        # All four envs should find the same global dir
        assert len(result) > 0
        for _, _, scope in result:
            assert "global" in scope

    def test_multiple_environments_detected(self, tmp_dir):
        """Multiple local directories should all be detected."""
        from utils.common import detect_environments
        (tmp_dir / ".gemini").mkdir()
        (tmp_dir / ".agents").mkdir()
        (tmp_dir / ".claude").mkdir()

        def mock_expanduser(path):
            return str(tmp_dir / "fake_home" / path.lstrip("~/"))

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()
        keys = [r[0] for r in result]
        assert "gemini" in keys
        assert "agents" in keys
        assert "claude" in keys
        assert len(result) >= 3

    def test_both_local_and_global(self, tmp_dir):
        """When both local and global exist, scope should show both."""
        from utils.common import detect_environments

        # Create local dir
        (tmp_dir / ".gemini").mkdir()

        global_dir = tmp_dir / "global_gemini"
        global_dir.mkdir()

        original_expanduser = os.path.expanduser

        def mock_expanduser(path):
            if path == "~/.gemini":
                return str(global_dir)
            return original_expanduser(path)

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()

        gemini = [r for r in result if r[0] == "gemini"]
        assert len(gemini) == 1
        assert "local" in gemini[0][2]
        assert "global" in gemini[0][2]

    def test_return_type_is_list_of_tuples(self, tmp_dir):
        """Each element should be a 3-tuple (key, label, scope_str)."""
        from utils.common import detect_environments
        (tmp_dir / ".gemini").mkdir()
        result = detect_environments()
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 3

    def test_label_matches_environments_config(self, tmp_dir):
        """Returned label should match the ENVIRONMENTS definition."""
        from utils.common import detect_environments
        from constants.environments import ENVIRONMENTS
        (tmp_dir / ".gemini").mkdir()
        result = detect_environments()
        gemini = [r for r in result if r[0] == "gemini"][0]
        assert gemini[1] == ENVIRONMENTS["gemini"]["label"]

    def test_file_not_detected_as_environment(self, tmp_dir):
        """A file named .gemini (not a directory) should not be detected."""
        from utils.common import detect_environments
        (tmp_dir / ".gemini").write_text("not a directory")

        def mock_expanduser(path):
            return str(tmp_dir / "fake_home" / path.lstrip("~/"))

        with patch("utils.common.os.path.expanduser", side_effect=mock_expanduser):
            result = detect_environments()
        keys = [r[0] for r in result]
        assert "gemini" not in keys
