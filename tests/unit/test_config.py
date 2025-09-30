"""Tests for configuration module."""

from pathlib import Path

from csv2pg_ai_schema_infer.config import Config


def test_default_config():
    """Test loading default configuration."""
    config = Config()

    assert config.sampling.rows == 100
    assert config.chunking.columns_per_chunk == 20
    assert config.llm.provider == "gemini"
    assert config.output.directory == Path("./output")


def test_config_from_yaml(tmp_path):
    """Test loading configuration from YAML."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
sampling:
  rows: 200
chunking:
  columns_per_chunk: 30
"""
    )

    config = Config.from_yaml(config_file)

    assert config.sampling.rows == 200
    assert config.chunking.columns_per_chunk == 30


def test_config_env_override(monkeypatch):
    """Test environment variable overrides."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")

    config = Config()

    assert config.gemini_api_key == "test-api-key"
    assert config.database_url == "postgresql://test:test@localhost/test"
