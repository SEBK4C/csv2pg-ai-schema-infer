"""Configuration management for CSV2PG AI Schema Infer."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SamplingConfig(BaseSettings):
    """CSV sampling configuration."""

    rows: int = Field(default=100, ge=1, le=10000)
    encoding: str = Field(default="utf-8")

    model_config = SettingsConfigDict(env_prefix="CSV2PG_SAMPLING_")


class ChunkingConfig(BaseSettings):
    """Column chunking configuration."""

    columns_per_chunk: int = Field(default=20, ge=1, le=200)
    parallel_requests: bool = Field(default=True)

    model_config = SettingsConfigDict(env_prefix="CSV2PG_CHUNKING_")


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    provider: str = Field(default="gemini")
    model: str = Field(default="gemini-1.5-pro")
    timeout: int = Field(default=30, ge=1, le=300)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_delay: int = Field(default=5, ge=1, le=60)

    model_config = SettingsConfigDict(env_prefix="CSV2PG_LLM_")


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    connection_template: str = Field(
        default="postgresql://{user}:{password}@{host}:{port}/{dbname}"
    )

    model_config = SettingsConfigDict(env_prefix="CSV2PG_DATABASE_")


class OutputConfig(BaseSettings):
    """Output configuration."""

    directory: Path = Field(default=Path("./output"))
    dry_run: bool = Field(default=False)

    @field_validator("directory", mode="before")
    @classmethod
    def validate_directory(cls, v: Any) -> Path:
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v

    model_config = SettingsConfigDict(env_prefix="CSV2PG_OUTPUT_")


class Config(BaseSettings):
    """Main configuration."""

    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    # API Keys
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    database_url: str = Field(default="", env="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "Config":
        """Load configuration from YAML file."""
        if not yaml_path.exists():
            return cls()

        with open(yaml_path) as f:
            data = yaml.safe_load(f) or {}

        # Create nested config objects
        config_data = {
            "sampling": SamplingConfig(**data.get("sampling", {})),
            "chunking": ChunkingConfig(**data.get("chunking", {})),
            "llm": LLMConfig(**data.get("llm", {})),
            "database": DatabaseConfig(**data.get("database", {})),
            "output": OutputConfig(**data.get("output", {})),
        }

        return cls(**config_data)


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to YAML configuration file. If None, uses default.

    Returns:
        Loaded configuration.
    """
    if config_path is None:
        # Look for default config
        default_path = Path("config/default.yaml")
        if default_path.exists():
            config_path = default_path

    if config_path and config_path.exists():
        return Config.from_yaml(config_path)

    # Return default config with env overrides
    return Config()
