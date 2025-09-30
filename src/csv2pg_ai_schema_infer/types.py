"""Type definitions for CSV2PG AI Schema Infer."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    """Confidence level for type inference."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ImportPhase(str, Enum):
    """Import process phases."""

    SAMPLING = "sampling"
    SAMPLED = "sampled"
    INFERRING = "inferring"
    INFERRED = "inferred"
    GENERATING = "generating"
    GENERATED = "generated"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportStatus(str, Enum):
    """Import status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class CSVProperties(BaseModel):
    """CSV file properties."""

    delimiter: str = Field(description="Column delimiter")
    encoding: str = Field(description="File encoding")
    quote_char: str = Field(default='"', description="Quote character")
    has_header: bool = Field(default=True, description="Has header row")
    row_count: int | None = Field(default=None, description="Total row count")
    column_count: int = Field(description="Number of columns")


class ColumnSample(BaseModel):
    """Sample data for a column."""

    name: str = Field(description="Column name")
    values: list[Any] = Field(description="Sample values")
    null_count: int = Field(default=0, description="Number of null values")
    total_count: int = Field(description="Total number of samples")

    @property
    def null_percentage(self) -> float:
        """Calculate percentage of null values."""
        if self.total_count == 0:
            return 0.0
        return (self.null_count / self.total_count) * 100


class CSVSample(BaseModel):
    """Sampled CSV data."""

    path: Path = Field(description="CSV file path")
    properties: CSVProperties = Field(description="CSV properties")
    headers: list[str] = Field(description="Column headers")
    rows: list[dict[str, Any]] = Field(description="Sample rows as dicts")
    sample_size: int = Field(description="Number of rows sampled")


class InferredType(BaseModel):
    """Inferred PostgreSQL type for a column."""

    column_name: str = Field(description="Column name")
    pg_type: str = Field(description="PostgreSQL type")
    confidence: ConfidenceLevel = Field(description="Confidence level")
    reasoning: str = Field(description="Reason for type choice")
    nullable: bool = Field(default=True, description="Can be NULL")
    constraints: list[str] = Field(default_factory=list, description="Type constraints")
    cast_rule: str | None = Field(
        default=None, description="Custom cast rule for pgloader"
    )


class ColumnSchema(BaseModel):
    """Schema for a single column."""

    name: str = Field(description="Column name")
    pg_type: str = Field(description="PostgreSQL type")
    nullable: bool = Field(default=True)
    constraints: list[str] = Field(default_factory=list)
    cast_rule: str | None = Field(default=None)

    @property
    def needs_cast(self) -> bool:
        """Check if column needs custom casting."""
        return self.cast_rule is not None


class TableSchema(BaseModel):
    """Complete table schema."""

    table_name: str = Field(description="Table name")
    columns: list[ColumnSchema] = Field(description="Column schemas")
    primary_key: str | None = Field(default=None, description="Primary key column")

    def get_column(self, name: str) -> ColumnSchema | None:
        """Get column by name."""
        for col in self.columns:
            if col.name == name:
                return col
        return None


class ColumnChunk(BaseModel):
    """A chunk of columns for processing."""

    chunk_id: int = Field(description="Chunk identifier")
    total_chunks: int = Field(description="Total number of chunks")
    columns: list[str] = Field(description="Column names in this chunk")
    sample_data: list[dict[str, Any]] = Field(description="Sample data for columns")


class ImportState(BaseModel):
    """State of an import operation."""

    version: str = Field(default="1.0")
    csv_path: Path
    csv_checksum: str = Field(description="SHA256 checksum of CSV file")
    table_name: str
    status: ImportStatus
    phase: ImportPhase
    timestamps: dict[str, datetime | None] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = Field(default=None)

    def mark_phase(self, phase: ImportPhase) -> None:
        """Mark a phase as completed."""
        self.phase = phase
        self.timestamps[phase.value] = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark import as failed."""
        self.status = ImportStatus.FAILED
        self.phase = ImportPhase.FAILED
        self.error = error
        self.timestamps["failed"] = datetime.now()

    def mark_completed(self) -> None:
        """Mark import as completed."""
        self.status = ImportStatus.COMPLETED
        self.phase = ImportPhase.COMPLETED
        self.timestamps["completed"] = datetime.now()


class GenerationResult(BaseModel):
    """Result of file generation."""

    pgloader_config_path: Path
    import_script_path: Path
    state_file_path: Path
    log_file_path: Path