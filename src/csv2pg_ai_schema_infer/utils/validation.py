"""Validation utilities for CSV2PG AI Schema Infer."""

import hashlib
import json
from pathlib import Path
from typing import Any

from ..types import InferredType, TableSchema


def validate_inferred_type(data: dict[str, Any]) -> InferredType:
    """
    Validate and parse inferred type data from LLM response.

    Args:
        data: Dictionary containing type information

    Returns:
        Validated InferredType

    Raises:
        ValueError: If data is invalid
    """
    required_fields = ["column_name", "postgresql_type", "confidence", "reasoning"]
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    # Normalize field names (handle both snake_case and variations)
    normalized = {
        "column_name": data.get("column_name") or data.get("name"),
        "pg_type": data.get("postgresql_type") or data.get("pg_type"),
        "confidence": data.get("confidence", "medium"),
        "reasoning": data.get("reasoning", ""),
        "nullable": data.get("nullable", True),
        "constraints": data.get("constraints", []),
        "cast_rule": data.get("cast_rule"),
    }

    return InferredType(**normalized)


def validate_table_schema(schema: TableSchema) -> bool:
    """
    Validate table schema for consistency.

    Args:
        schema: Table schema to validate

    Returns:
        True if valid

    Raises:
        ValueError: If schema is invalid
    """
    if not schema.columns:
        raise ValueError("Schema must have at least one column")

    # Check for duplicate column names
    column_names = [col.name for col in schema.columns]
    duplicates = [name for name in column_names if column_names.count(name) > 1]
    if duplicates:
        raise ValueError(f"Duplicate column names: {', '.join(set(duplicates))}")

    # Validate primary key exists
    if schema.primary_key:
        if schema.primary_key not in column_names:
            raise ValueError(
                f"Primary key '{schema.primary_key}' not found in columns"
            )

    return True


def compute_file_checksum(file_path: Path, algorithm: str = "sha256") -> str:
    """
    Compute checksum of a file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)

    Returns:
        Hex digest of file checksum
    """
    hash_func = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return f"{algorithm}:{hash_func.hexdigest()}"


def validate_json_file(file_path: Path) -> dict[str, Any]:
    """
    Validate and load JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data

    Raises:
        ValueError: If file is not valid JSON
    """
    try:
        with open(file_path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}") from e


def validate_postgresql_type(pg_type: str) -> bool:
    """
    Check if PostgreSQL type is valid.

    Args:
        pg_type: PostgreSQL type name

    Returns:
        True if valid type
    """
    # Common PostgreSQL types
    valid_types = {
        # Numeric
        "smallint",
        "integer",
        "int",
        "bigint",
        "decimal",
        "numeric",
        "real",
        "double precision",
        "smallserial",
        "serial",
        "bigserial",
        # Monetary
        "money",
        # Character
        "varchar",
        "char",
        "text",
        # Binary
        "bytea",
        # Date/Time
        "timestamp",
        "timestamptz",
        "timestamp with time zone",
        "timestamp without time zone",
        "date",
        "time",
        "timetz",
        "interval",
        # Boolean
        "boolean",
        "bool",
        # Enumerated
        "enum",
        # Geometric
        "point",
        "line",
        "lseg",
        "box",
        "path",
        "polygon",
        "circle",
        # Network
        "cidr",
        "inet",
        "macaddr",
        # UUID
        "uuid",
        # JSON
        "json",
        "jsonb",
        # Arrays (basic check)
        "array",
        # XML
        "xml",
    }

    # Extract base type (handle varchar(255), numeric(10,2), etc.)
    base_type = pg_type.split("(")[0].strip().lower()

    return base_type in valid_types