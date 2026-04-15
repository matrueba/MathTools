"""
Tests for src/constants/ modules.
Covers: general.py, environments.py, repositories.py
"""

import pytest


# ── general.py ───────────────────────────────────────────────────────────────

class TestVersion:
    def test_version_is_string(self):
        from constants.general import VERSION
        assert isinstance(VERSION, str)

    def test_version_format(self):
        """VERSION should follow semver (major.minor.patch)."""
        from constants.general import VERSION
        parts = VERSION.split(".")
        assert len(parts) == 3, f"Expected semver, got {VERSION}"
        for part in parts:
            assert part.isdigit(), f"Non-numeric version component: {part}"

    def test_version_value(self):
        from constants.general import VERSION
        assert VERSION == "1.0.0"


# ── environments.py ─────────────────────────────────────────────────────────

class TestEnvironments:
    def test_environments_is_dict(self):
        from constants.environments import ENVIRONMENTS
        assert isinstance(ENVIRONMENTS, dict)

    def test_expected_keys_exist(self):
        from constants.environments import ENVIRONMENTS
        expected = {"gemini", "agents", "opencode", "claude"}
        assert set(ENVIRONMENTS.keys()) == expected

    @pytest.mark.parametrize("env_key", ["gemini", "agents", "opencode", "claude"])
    def test_environment_has_required_fields(self, env_key):
        from constants.environments import ENVIRONMENTS
        env = ENVIRONMENTS[env_key]
        required_fields = ["label", "description", "target_dir", "global_dir", "sources"]
        for field in required_fields:
            assert field in env, f"Missing field '{field}' in environment '{env_key}'"

    @pytest.mark.parametrize("env_key", ["gemini", "agents", "opencode", "claude"])
    def test_label_is_non_empty_string(self, env_key):
        from constants.environments import ENVIRONMENTS
        assert isinstance(ENVIRONMENTS[env_key]["label"], str)
        assert len(ENVIRONMENTS[env_key]["label"]) > 0

    @pytest.mark.parametrize("env_key", ["gemini", "agents", "opencode", "claude"])
    def test_target_dir_starts_with_dot(self, env_key):
        from constants.environments import ENVIRONMENTS
        assert ENVIRONMENTS[env_key]["target_dir"].startswith(".")

    @pytest.mark.parametrize("env_key", ["gemini", "agents", "opencode", "claude"])
    def test_sources_is_list_of_tuples(self, env_key):
        from constants.environments import ENVIRONMENTS
        sources = ENVIRONMENTS[env_key]["sources"]
        assert isinstance(sources, list)
        assert len(sources) > 0
        for source in sources:
            assert len(source) == 4, f"Source tuple should have 4 elements, got {len(source)}"

    @pytest.mark.parametrize("env_key", ["gemini", "agents", "opencode", "claude"])
    def test_source_repo_names_are_valid(self, env_key):
        from constants.environments import ENVIRONMENTS
        from constants.repositories import REPOSITORIES
        for repo_name, _, _, _ in ENVIRONMENTS[env_key]["sources"]:
            assert repo_name in REPOSITORIES, (
                f"Source references unknown repository '{repo_name}'"
            )

    def test_gemini_specific(self):
        from constants.environments import ENVIRONMENTS
        env = ENVIRONMENTS["gemini"]
        assert env["target_dir"] == ".gemini"
        assert env["global_dir"] == "~/.gemini"

    def test_claude_specific(self):
        from constants.environments import ENVIRONMENTS
        env = ENVIRONMENTS["claude"]
        assert env["target_dir"] == ".claude"
        assert env["global_dir"] == "~/.claude"

    def test_opencode_specific(self):
        from constants.environments import ENVIRONMENTS
        env = ENVIRONMENTS["opencode"]
        assert env["target_dir"] == ".opencode"
        assert env["global_dir"] == "~/.config/opencode"

    def test_agents_specific(self):
        from constants.environments import ENVIRONMENTS
        env = ENVIRONMENTS["agents"]
        assert env["target_dir"] == ".agents"
        assert env["global_dir"] == "~/.agents"


# ── repositories.py ─────────────────────────────────────────────────────────

class TestRepositories:
    def test_repositories_is_dict(self):
        from constants.repositories import REPOSITORIES
        assert isinstance(REPOSITORIES, dict)

    def test_expected_repos_exist(self):
        from constants.repositories import REPOSITORIES
        expected = {"framework", "skills"}
        assert set(REPOSITORIES.keys()) == expected

    @pytest.mark.parametrize("repo_key", ["framework", "skills"])
    def test_repo_has_url_and_prefix(self, repo_key):
        from constants.repositories import REPOSITORIES
        repo = REPOSITORIES[repo_key]
        assert "url" in repo
        assert "prefix" in repo

    @pytest.mark.parametrize("repo_key", ["framework", "skills"])
    def test_repo_url_is_github_zip(self, repo_key):
        from constants.repositories import REPOSITORIES
        url = REPOSITORIES[repo_key]["url"]
        assert url.startswith("https://github.com/")
        assert url.endswith(".zip")

    @pytest.mark.parametrize("repo_key", ["framework", "skills"])
    def test_repo_prefix_ends_with_slash(self, repo_key):
        from constants.repositories import REPOSITORIES
        prefix = REPOSITORIES[repo_key]["prefix"]
        assert prefix.endswith("/")

    def test_framework_url(self):
        from constants.repositories import REPOSITORIES
        assert "matrueba-AI-development-framework" in REPOSITORIES["framework"]["url"]

    def test_skills_url(self):
        from constants.repositories import REPOSITORIES
        assert "matrueba-skills-framework" in REPOSITORIES["skills"]["url"]
