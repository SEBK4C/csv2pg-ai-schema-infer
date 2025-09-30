"""Configuration management for CSV2PG AI Schema Infer."""

import multiprocessing
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
    model: str = Field(
        default="gemini-flash-latest",
        description=(
            "Gemini model: gemini-flash-latest (default), gemini-pro-latest, "
            "gemini-2.5-pro, gemini-2.0-flash, gemini-flash-lite-latest"
        )
    )
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


class PerformanceConfig(BaseSettings):
    """Performance settings for pgloader."""

    # CPU settings (auto-detect by default)
    workers: int = Field(
        default_factory=lambda: max(4, multiprocessing.cpu_count() // 2),
        description="Number of parallel worker threads for CSV reading",
    )
    concurrency: int = Field(
        default_factory=lambda: max(2, multiprocessing.cpu_count() // 4),
        description="Number of parallel PostgreSQL connections",
    )

    # Memory and batch settings
    batch_size: str = Field(
        default="50MB", description="Size of data chunks sent to PostgreSQL"
    )
    prefetch_rows: int = Field(
        default=25000, description="Number of rows to buffer in memory"
    )
    work_mem: str = Field(
        default="512MB", description="Per-operation memory for sorting/hashing"
    )
    maintenance_work_mem: str = Field(
        default="2GB", description="Memory for index creation and maintenance"
    )

    model_config = SettingsConfigDict(env_prefix="CSV2PG_PERFORMANCE_")

    @classmethod
    def auto_detect(cls, file_size_gb: float | None = None) -> "PerformanceConfig":
        """
        Auto-detect optimal settings based on system resources and file size.

        Args:
            file_size_gb: File size in gigabytes (optional)

        Returns:
            Performance configuration optimized for the environment
        """
        cpu_cores = multiprocessing.cpu_count()

        # Scale workers based on CPU cores
        if cpu_cores >= 32:
            workers = 16
            concurrency = 8
        elif cpu_cores >= 16:
            workers = 8
            concurrency = 4
        elif cpu_cores >= 8:
            workers = 4
            concurrency = 2
        else:
            workers = max(2, cpu_cores // 2)
            concurrency = max(1, workers // 2)

        # Scale batch size and prefetch based on file size
        if file_size_gb and file_size_gb > 5:
            batch_size = "100MB"
            prefetch_rows = 50000
        elif file_size_gb and file_size_gb > 1:
            batch_size = "50MB"
            prefetch_rows = 25000
        else:
            batch_size = "25MB"
            prefetch_rows = 10000

        # Memory settings (conservative defaults)
        work_mem = "512MB"
        maintenance_work_mem = "2GB"

        return cls(
            workers=workers,
            concurrency=concurrency,
            batch_size=batch_size,
            prefetch_rows=prefetch_rows,
            work_mem=work_mem,
            maintenance_work_mem=maintenance_work_mem,
        )


class Config(BaseSettings):
    """Main configuration."""

    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    # API Keys
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    database_url: str = Field(default="", env="DATABASE_URL")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="allow"
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
            "performance": PerformanceConfig(**data.get("performance", {})),
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
