"""Tests for CSV sampler module."""

import pytest

from csv2pg_ai_schema_infer.sampler import detect_csv_properties, sample_csv


def test_sample_csv_simple(sample_csv_simple):
    """Test sampling a simple CSV file."""
    sample = sample_csv(sample_csv_simple, n_rows=10)

    assert sample.sample_size == 3  # Only 3 rows in the file
    assert len(sample.headers) == 4
    assert sample.headers == ["id", "name", "age", "email"]
    assert sample.properties.delimiter == ","
    assert sample.properties.column_count == 4


def test_sample_csv_with_types(sample_csv_types):
    """Test sampling CSV with various data types."""
    sample = sample_csv(sample_csv_types, n_rows=10)

    assert sample.sample_size == 3
    assert len(sample.headers) == 9
    assert "uuid_col" in sample.headers
    assert "timestamp_col" in sample.headers


def test_sample_csv_unicode(sample_csv_unicode):
    """Test sampling CSV with Unicode characters."""
    sample = sample_csv(sample_csv_unicode, n_rows=10)

    assert sample.sample_size == 3
    assert len(sample.headers) == 3
    # Check that Unicode is preserved
    assert any("François" in str(row.values()) for row in sample.rows)


def test_sample_csv_empty(sample_csv_empty):
    """Test sampling an empty CSV."""
    with pytest.raises(ValueError, match="empty"):
        sample_csv(sample_csv_empty, n_rows=10)


def test_sample_csv_nonexistent():
    """Test sampling a non-existent CSV."""
    from pathlib import Path

    with pytest.raises(FileNotFoundError):
        sample_csv(Path("/tmp/nonexistent.csv"))


def test_detect_csv_properties(sample_csv_simple):
    """Test CSV property detection."""
    properties = detect_csv_properties(sample_csv_simple)

    assert properties.delimiter == ","
    assert properties.has_header is True
    assert properties.column_count == 4
    assert properties.encoding in ["utf-8", "ascii"]
