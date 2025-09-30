"""Shared test fixtures for CSV2PG AI Schema Infer tests."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary directory for test outputs."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_csv_simple(tmp_path):
    """Generate a simple test CSV."""
    csv_path = tmp_path / "test_simple.csv"
    content = """id,name,age,email
1,John Doe,25,john@example.com
2,Jane Smith,32,jane@example.com
3,Bob Johnson,28,bob@example.com
"""
    csv_path.write_text(content)
    return csv_path


@pytest.fixture
def sample_csv_types(tmp_path):
    """Generate CSV with various data types."""
    csv_path = tmp_path / "test_types.csv"
    content = """id,uuid_col,int_col,bigint_col,decimal_col,bool_col,date_col,timestamp_col,text_col
1,550e8400-e29b-41d4-a716-446655440000,42,9223372036854775807,123.45,true,2024-01-15,2024-01-15T10:30:00,Hello World
2,6ba7b810-9dad-11d1-80b4-00c04fd430c8,100,9223372036854775806,456.78,false,2024-01-16,2024-01-16T14:22:00,Test Data
3,f47ac10b-58cc-4372-a567-0e02b2c3d479,200,9223372036854775805,789.01,true,2024-01-17,2024-01-17T09:15:00,Sample Text
"""
    csv_path.write_text(content)
    return csv_path


@pytest.fixture
def sample_csv_unicode(tmp_path):
    """Generate CSV with Unicode characters."""
    csv_path = tmp_path / "test_unicode.csv"
    content = """id,name,description
1,François,Café ☕
2,José,Piñata 🎉
3,李明,你好世界 🌍
"""
    csv_path.write_text(content, encoding="utf-8")
    return csv_path


@pytest.fixture
def sample_csv_empty(tmp_path):
    """Generate an empty CSV."""
    csv_path = tmp_path / "test_empty.csv"
    content = """id,name,value
"""
    csv_path.write_text(content)
    return csv_path