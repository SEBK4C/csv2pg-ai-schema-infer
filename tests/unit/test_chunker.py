"""Tests for column chunker module."""

import pytest

from csv2pg_ai_schema_infer.chunker import chunk_columns, chunk_columns_smart
from csv2pg_ai_schema_infer.sampler import sample_csv


def test_chunk_columns_basic(sample_csv_simple):
    """Test basic column chunking."""
    sample = sample_csv(sample_csv_simple)
    chunks = chunk_columns(sample, chunk_size=2)

    assert len(chunks) == 2  # 4 columns / 2 = 2 chunks
    assert chunks[0].chunk_id == 0
    assert chunks[0].total_chunks == 2
    assert len(chunks[0].columns) == 2
    assert len(chunks[1].columns) == 2


def test_chunk_columns_all_in_one(sample_csv_simple):
    """Test chunking when all columns fit in one chunk."""
    sample = sample_csv(sample_csv_simple)
    chunks = chunk_columns(sample, chunk_size=10)

    assert len(chunks) == 1
    assert len(chunks[0].columns) == 4


def test_chunk_columns_smart(sample_csv_simple):
    """Test smart chunking."""
    sample = sample_csv(sample_csv_simple)
    chunks = chunk_columns_smart(sample, chunk_size=2)

    assert len(chunks) >= 1
    # Verify all columns are included
    all_columns = []
    for chunk in chunks:
        all_columns.extend(chunk.columns)
    assert sorted(all_columns) == sorted(sample.headers)


def test_chunk_columns_preserves_all(sample_csv_types):
    """Test that chunking preserves all columns."""
    sample = sample_csv(sample_csv_types)
    chunks = chunk_columns(sample, chunk_size=3)

    all_columns = []
    for chunk in chunks:
        all_columns.extend(chunk.columns)

    assert len(all_columns) == len(sample.headers)
    assert sorted(all_columns) == sorted(sample.headers)