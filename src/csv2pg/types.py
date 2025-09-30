"""Core type definitions for CSV2PG."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class ImportMode(str, Enum):
    """Import mode for handling existing data."""
    
    OVERWRITE = "overwrite"  # Drop table and recreate (default)
    APPEND = "append"        # Insert new rows, keep existing
    UPSERT = "upsert"        # Insert or update based on primary keys
    SKIP = "skip"            # Insert only new rows, skip duplicates


class OnConflictAction(str, Enum):
    """Action to take on conflict during upsert."""
    
    UPDATE = "update"        # Update existing row with new values
    NOTHING = "nothing"      # Skip the conflicting row


class SchemaEvolution(str, Enum):
    """How to handle schema changes."""
    
    FAIL = "fail"            # Fail if schema doesn't match
    ADD_COLUMNS = "add_columns"  # Add new columns, keep existing


class ConfidenceLevel(str, Enum):
    """Confidence level for type inference."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ColumnSample(BaseModel):
    """Sample data for a single column."""
    
    name: str
    values: List[Optional[str]] = Field(default_factory=list)
    null_count: int = 0
    unique_count: int = 0
    total_count: int = 0


class InferredType(BaseModel):
    """Inferred PostgreSQL type for a column."""
    
    column_name: str
    postgresql_type: str
    confidence: ConfidenceLevel
    reasoning: str
    nullable: bool = True
    constraints: List[str] = Field(default_factory=list)
    needs_cast: bool = False
    cast_rule: Optional[str] = None


class ColumnSchema(BaseModel):
    """Final column schema for PostgreSQL."""
    
    name: str
    pg_type: str
    nullable: bool = True
    constraints: List[str] = Field(default_factory=list)
    needs_cast: bool = False
    cast_rule: Optional[str] = None


class TableSchema(BaseModel):
    """Complete table schema."""
    
    table_name: str
    columns: List[ColumnSchema]
    primary_key: Optional[List[str]] = None
    
    @validator('primary_key', pre=True)
    def validate_primary_key(cls, v, values):
        """Ensure primary key columns exist in the schema."""
        if v is None:
            return v
        
        column_names = {col.name for col in values.get('columns', [])}
        missing = set(v) - column_names
        if missing:
            raise ValueError(f"Primary key columns not found: {missing}")
        return v


class CSVSample(BaseModel):
    """Sample data from a CSV file."""
    
    headers: List[str]
    rows: List[Dict[str, Optional[str]]]
    delimiter: str = ","
    encoding: str = "utf-8"
    has_header: bool = True
    total_rows: Optional[int] = None
    file_size: Optional[int] = None


class ImportState(BaseModel):
    """State tracking for import operations."""
    
    version: str = "1.0"
    csv_path: Path
    csv_checksum: Optional[str] = None
    table_name: str
    status: str = "pending"  # pending, in_progress, completed, failed
    phase: str = "sampling"  # sampling, inferring, generating, importing
    import_mode: ImportMode = ImportMode.OVERWRITE
    primary_keys: List[str] = Field(default_factory=list)
    on_conflict: OnConflictAction = OnConflictAction.UPDATE
    
    timestamps: Dict[str, Optional[str]] = Field(default_factory=dict)
    progress: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    
    # Metrics
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0


class GenerationResult(BaseModel):
    """Result of file generation."""
    
    pgloader_config: Path
    import_script: Path
    merge_sql: Optional[Path] = None
    state_file: Path
    log_file: Path
    dry_run: bool = False


class ImportMetrics(BaseModel):
    """Metrics for import operations."""
    
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Row counts
    rows_total: int = 0
    rows_processed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_skipped: int = 0
    rows_failed: int = 0
    
    # Performance
    sampling_duration: Optional[float] = None
    inference_duration: Optional[float] = None
    generation_duration: Optional[float] = None
    import_duration: Optional[float] = None
    
    # Memory usage
    peak_memory_mb: Optional[float] = None
